import customtkinter as ctk
import threading
import sys
import os
import shutil
import time
from pathlib import Path
from tkinter import filedialog, messagebox
import main 
import nodes 
import detective 

# Intentamos importar Drag & Drop
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    class AchillesBase(ctk.CTk, TkinterDnD.Tk):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
    DRAG_DROP_AVAILABLE = True
except ImportError:
    class AchillesBase(ctk.CTk): pass
    DRAG_DROP_AVAILABLE = False

# --- CONFIGURACIÓN DE ESTILO ---
ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("green") 

class TextRedirector(object):
    def __init__(self, widget):
        self.widget = widget
    def write(self, str):
        try:
            self.widget.configure(state="normal")
            self.widget.insert("end", str)
            self.widget.see("end") 
            self.widget.configure(state="disabled")
        except: pass
    def flush(self): pass

class TextEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, initial_text=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x600")
        self.attributes("-topmost", True)
        self.result_path = None
        self.parent_app = parent
        
        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 14), wrap="none")
        self.textbox.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        if initial_text: self.textbox.insert("0.0", initial_text)
            
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        btn_save = ctk.CTkButton(btn_frame, text="💾 Guardar", command=self.save_content, fg_color="#00835D", width=150)
        btn_save.pack(side="left", padx=10)
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancelar", command=self.close_window, fg_color="#555", width=100)
        btn_cancel.pack(side="left", padx=10)
        
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.lift(); self.focus_force()

    def save_content(self):
        content = self.textbox.get("0.0", "end").strip()
        if not content: self.close_window(); return
        filename = f"temp_editor_{int(time.time())}.txt"
        path = os.path.abspath(os.path.join(main.DOCS_DIR, filename))
        os.makedirs(main.DOCS_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        self.result_path = path
        self.close_window()

    def close_window(self):
        self.parent_app.active_editor = None
        self.destroy()

class AchillesApp(AchillesBase):
    def __init__(self):
        super().__init__()
        self.title("Achilles | Batch Optimizer Commander")
        self.geometry("1150x950")
        
        # --- ESTADO ---
        self.pdf_path = None
        self.expected_path = None
        self.initial_prompt_path = None 
        self.active_editor = None
        self.imported_count = 0 

        # --- LAYOUT INTELIGENTE ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(9, weight=10) 

        # 0. HEADER COMPACTO
        self.lbl_header = ctk.CTkLabel(self, text="ACHILLES | Master Prompts", font=("Roboto Medium", 18), text_color="#2CC985")
        self.lbl_header.grid(row=0, column=0, columnspan=3, pady=(10, 5), sticky="w", padx=20)

        # 1. API KEY & FAMILIA
        frm_top = ctk.CTkFrame(self, fg_color="transparent")
        frm_top.grid(row=1, column=0, columnspan=3, padx=20, pady=5, sticky="ew")
        
        ctk.CTkLabel(frm_top, text="API Key:", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 5))
        self.entry_api = ctk.CTkEntry(frm_top, width=200, show="●")
        self.entry_api.pack(side="left", padx=5)
        
        ctk.CTkLabel(frm_top, text="Familia ID:", font=("Arial", 12, "bold")).pack(side="left", padx=(20, 5))
        self.entry_family = ctk.CTkEntry(frm_top, width=200, placeholder_text="ej: 8797esp")
        self.entry_family.pack(side="left", padx=5)
        self.entry_family.bind("<KeyRelease>", self.update_batch_status)

        # --- ZONA DE CARGA ---
        self.frm_upload = ctk.CTkFrame(self, fg_color="#2B2B2B")
        self.frm_upload.grid(row=2, column=0, columnspan=3, padx=20, pady=10, sticky="ew")
        self.frm_upload.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.frm_upload, text="COLA DE PROCESAMIENTO", font=("Arial", 11, "bold"), text_color="gray").grid(row=0, column=0, columnspan=3, pady=5)

        self.create_input_row(self.frm_upload, 1, "Documento:", "Cargar PDF", "pdf_path", [("Docs", "*.pdf *.jpg")])
        self.create_input_row(self.frm_upload, 2, "Datos Esperados:", "Cargar JSON", "expected_path", [("Data", "*.txt *.json")], allow_edit=True)

        self.btn_add = ctk.CTkButton(self.frm_upload, text="⬇️ AGREGAR AL LOTE", command=self.add_case_to_batch, fg_color="#444", hover_color="#555", height=25)
        self.btn_add.grid(row=3, column=0, columnspan=4, pady=10)

        # 4. STATUS (Fila 4)
        self.lbl_batch_status = ctk.CTkLabel(self, text="📂 Lote: 0 documentos listos.", font=("Arial", 14, "bold"), text_color="#FFA500", anchor="w")
        self.lbl_batch_status.grid(row=4, column=0, columnspan=3, padx=30, pady=5, sticky="w")

        # 5. PROMPT BASE (Fila 5 - NUEVA FUNCIÓN)
        # Ahora usamos create_input_row para que tenga Editar/Borrar igual que los demás
        self.create_input_row(self, 5, "📝 Prompt Base:", "Cargar Txt", "initial_prompt_path", [("Txt", "*.txt")], allow_edit=True)

        # 6. BOTONES DE ACCIÓN (Fila 6 y 7)
        self.btn_run = ctk.CTkButton(self, text="▶️ EJECUTAR OPTIMIZACIÓN", command=self.start_batch_process, fg_color="#00835D", hover_color="#006648", height=40, font=("Roboto", 14, "bold"))
        self.btn_run.grid(row=6, column=0, columnspan=3, padx=30, pady=(15, 5), sticky="ew")

        self.btn_reset = ctk.CTkButton(self, text="🗑️ NUEVA SESIÓN (LIMPIAR)", command=self.reset_session, fg_color="#8B0000", hover_color="#B22222", height=30)
        self.btn_reset.grid(row=7, column=0, columnspan=3, padx=30, pady=5)

        # 9. LOGS
        ctk.CTkLabel(self, text="Registro de Auditoría:", text_color="gray").grid(row=8, column=0, padx=20, sticky="w", pady=(10,0))
        self.textbox_log = ctk.CTkTextbox(self, font=("Consolas", 10), text_color="#E0E0E0", fg_color="#1A1A1A")
        self.textbox_log.grid(row=9, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="nsew")
        
        sys.stdout = TextRedirector(self.textbox_log)
        sys.stderr = TextRedirector(self.textbox_log)

        self.cleanup_temp_files()

    def reset_session(self):
        """Elimina todos los archivos cargados para empezar de cero."""
        if not messagebox.askyesno("Confirmar Limpieza", "¿Seguro que quieres borrar todos los documentos cargados y empezar una nueva sesión?"):
            return
            
        print("\n🧹 Iniciando limpieza de sesión...")
        
        # --- TRUCO PARA WINDOWS/ONEDRIVE ---
        # Esta función fuerza el borrado quitando el atributo "Solo Lectura"
        def force_remove_readonly(func, path, excinfo):
            import stat
            os.chmod(path, stat.S_IWRITE) 
            func(path)
            
        try:
            if main.DOCS_DIR.exists():
                # Intentamos borrar usando el "handler" de fuerza bruta
                shutil.rmtree(main.DOCS_DIR, onerror=force_remove_readonly)
            
            # Esperamos un microsegundo para que Windows libere el handle
            time.sleep(0.5)
            
            # Recreamos la carpeta limpia
            os.makedirs(main.DOCS_DIR, exist_ok=True)
            
            # Limpiar variables de GUI
            self.clear_input("pdf_path", self.lbl_pdf_path)
            self.clear_input("expected_path", self.lbl_expected_path)
            self.clear_input("initial_prompt_path", self.lbl_initial_prompt_path)
            self.entry_family.delete(0, 'end')
            
            self.update_batch_status()
            print("✅ Sesión reiniciada. Carpeta de casos vacía.")
            messagebox.showinfo("Limpieza", "Listo para una nueva familia.")
            
        except Exception as e:
            # Si falla aun así, es porque tienes el archivo ABIERTO en otra ventana
            print(f"⚠️ Error limpiando: {e}")
            messagebox.showerror("Error de Permisos", 
                                 f"Windows no dejó borrar la carpeta.\n\n"
                                 f"Posibles causas:\n"
                                 f"1. Tienes un PDF abierto.\n"
                                 f"2. OneDrive está sincronizando justo ahora.\n\n"
                                 f"Solución: Espera 10 segundos y prueba de nuevo.")

    # --- HELPERS UI ---
    def create_input_row(self, parent, row, label_text, btn_text, var_name, file_types, allow_edit=False):
        ctk.CTkLabel(parent, text=label_text, font=("Arial", 12)).grid(row=row, column=0, padx=30, pady=5, sticky="w")
        
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=1, columnspan=2, padx=30, pady=5, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        cmd_load = lambda: self.select_file(var_name, file_types, lbl_val)
        ctk.CTkButton(frame, text=btn_text, command=cmd_load, width=100, height=25).grid(row=0, column=0, padx=(0, 5))

        lbl_val = ctk.CTkLabel(frame, text="...", text_color="gray", anchor="w")
        lbl_val.grid(row=0, column=1, padx=5, sticky="ew")
        
        if DRAG_DROP_AVAILABLE:
            def on_drop(event):
                path = event.data.strip('{}')
                setattr(self, var_name, path)
                lbl_val.configure(text=os.path.basename(path), text_color="white")
            lbl_val.drop_target_register(DND_FILES); lbl_val.dnd_bind('<<Drop>>', on_drop)

        if allow_edit:
            cmd_edit = lambda: self.open_editor(var_name, lbl_val)
            ctk.CTkButton(frame, text="✏️", width=30, height=25, fg_color="#444", command=cmd_edit).grid(row=0, column=2, padx=5)

        cmd_clear = lambda: self.clear_input(var_name, lbl_val)
        ctk.CTkButton(frame, text="❌", width=30, height=25, fg_color="#C33", command=cmd_clear).grid(row=0, column=3, padx=5)
        setattr(self, f"lbl_{var_name}", lbl_val)

    def select_file(self, var_name, ftypes, lbl):
        f = filedialog.askopenfilename(filetypes=ftypes)
        if f: 
            setattr(self, var_name, f)
            if hasattr(lbl, "configure"): lbl.configure(text=os.path.basename(f), text_color="white")

    def clear_input(self, var_name, lbl):
        setattr(self, var_name, None)
        lbl.configure(text="...", text_color="gray")

    def open_editor(self, var_name, lbl):
        if self.active_editor: self.active_editor.lift(); return
        val = getattr(self, var_name)
        txt = ""
        if val and os.path.exists(val):
            try: txt = Path(val).read_text(encoding="utf-8")
            except: pass
        dialog = TextEditorDialog(self, f"Editor: {var_name}", txt)
        self.active_editor = dialog 
        self.wait_window(dialog) 
        if dialog.result_path:
            setattr(self, var_name, dialog.result_path)
            lbl.configure(text="[Editado Manualmente]", text_color="#FFA500")

    def cleanup_temp_files(self):
        for f in os.listdir("."):
            if f.startswith("temp_") and (f.endswith(".jpg") or f.endswith(".txt")):
                try: os.remove(f)
                except: pass

    def update_batch_status(self, event=None):
        fam = self.entry_family.get().strip()
        if not fam: self.lbl_batch_status.configure(text="📂 Esperando ID..."); return
        count = len(list(main.DOCS_DIR.glob(f"expected_*{fam}*.txt"))) if main.DOCS_DIR.exists() else 0
        self.lbl_batch_status.configure(text=f"📂 Familia '{fam}': {count} casos en cola.")
        self.imported_count = count

    def add_case_to_batch(self):
        fam = self.entry_family.get().strip()
        pdf = self.pdf_path
        exp = self.expected_path
        if not fam or not pdf or not exp: messagebox.showwarning("Faltan Datos", "Completa los campos antes de agregar."); return
        if not os.path.exists(pdf) or not os.path.exists(exp): messagebox.showerror("Error", "Archivos no encontrados."); return

        try:
            safe_name = Path(pdf).stem.replace(" ", "_")
            case_id = f"{fam}_{safe_name}"
            os.makedirs(main.DOCS_DIR, exist_ok=True)
            shutil.copy(pdf, main.DOCS_DIR / f"{case_id}{Path(pdf).suffix}")
            shutil.copy(exp, main.DOCS_DIR / f"expected_{case_id}.txt")
            print(f"✅ Agregado: {case_id}")
            self.clear_input("pdf_path", self.lbl_pdf_path)
            self.clear_input("expected_path", self.lbl_expected_path)
            self.update_batch_status()
        except Exception as e: messagebox.showerror("Error", str(e))

    def start_batch_process(self):
        api = self.entry_api.get().strip()
        fam = self.entry_family.get().strip()
        if not api or not fam: messagebox.showerror("Error", "Falta API Key o ID de Familia."); return
        if self.imported_count == 0: 
            if not messagebox.askyesno("¿Buscar?", "No cargaste nada nuevo. ¿Buscar casos existentes en carpeta?"): return

        self.btn_run.configure(state="disabled", text="⏳ EJECUTANDO...")
        threading.Thread(target=self.run_logic, args=(api, fam), daemon=True).start()

    def run_logic(self, api_key, family):
        try:
            print(f"\n{'='*40}\n🚀 ACHILLES BATCH: {family.upper()}\n{'='*40}")
            nodes.client.api_key = api_key; detective.client.api_key = api_key
            os.makedirs(main.PROMPTS_DIR, exist_ok=True)
            
            dest_master = main.PROMPTS_DIR / f"MASTER_{family}.txt"
            
            if self.initial_prompt_path:
                try:
                    if os.path.abspath(self.initial_prompt_path) != os.path.abspath(dest_master):
                        shutil.copy(self.initial_prompt_path, dest_master)
                        print(f"📝 Prompt Semilla copiado.")
                    else:
                        print(f"📝 Usando Prompt Semilla ya existente en destino.")
                except Exception as e:
                    print(f"⚠️ Nota: No se pudo copiar prompt inicial: {e}")

            result = main.run_family_batch(family)
            
            if result:
                score = result.get('best_avg_score', 0.0)
                tactic = result.get('best_tactic', "")
                original = result.get('original_prompt', "")
                
                print(f"\n👮‍♂️ INICIANDO PROTOCOLO DE FINALIZACIÓN (Sintaxis)...")
                
                expected_keys = []
                batch_q = result.get('batch_queue', [])
                if batch_q and 'expected_data' in batch_q[0]:
                    expected_keys = list(batch_q[0]['expected_data'].keys())
                
                separator = "=== OPTIMIZED TACTIC (Family Version) ==="
                if "=== ORIGINAL PROMPT ===" in original:
                     base_prompt = original.split("=== ORIGINAL PROMPT ===")[1].strip()
                else:
                     base_prompt = original.strip()

                raw_content = (
                    f"{separator}\n"
                    f"{tactic}\n\n"
                    f"=== ORIGINAL PROMPT ===\n"
                    f"{base_prompt}"
                )

                final_content = nodes.syntax_enforcer_agent(raw_content, expected_keys)
                
                print(f"\n✋ VALIDACIÓN REQUERIDA.")
                should_save = messagebox.askyesno(
                    "Validación de Resultados", 
                    f"El proceso finalizó con un Score Promedio de {score:.1f}%.\n\n"
                    f"¿Deseas SOBRESCRIBIR el Prompt Maestro actual con esta nueva versión optimizada?"
                )
                
                if should_save:
                    with open(dest_master, "w", encoding="utf-8") as f:
                        f.write(final_content)
                    print(f"✅ GUARDADO. Score: {score:.1f}%")
                    messagebox.showinfo("Éxito", "Prompt Maestro actualizado correctamente.")
                else:
                    print(f"🚫 Guardado cancelado por el usuario. Se mantiene la versión anterior.")
                    messagebox.showinfo("Cancelado", "No se realizaron cambios en el Prompt Maestro.")

            else: 
                print("❌ Sin resultados.")
        except Exception as e: print(f"❌ Error: {e}"); import traceback; traceback.print_exc()
        finally: 
            self.btn_run.configure(state="normal", text="▶️ EJECUTAR")
            self.update_batch_status()

if __name__ == "__main__":
    if not os.path.exists("casos_docs"): os.makedirs("casos_docs")
    if not os.path.exists("prompt_textos"): os.makedirs("prompt_textos")
    app = AchillesApp()
    app.mainloop()