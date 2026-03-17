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
        self.title("Achilles | Master Prompt")
        self.geometry("1150x950")
        
        # --- ESTADO ---
        self.pdf_path = None
        self.expected_path = None
        self.initial_prompt_path = None 
        self.active_editor = None
        self.imported_count = 0 

        # --- LAYOUT OPTIMIZADO ---
        # Configuramos la fila de los logs (fila 7) para que se expanda al máximo
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1) 

        # 0. HEADER COMPACTO
        self.lbl_header = ctk.CTkLabel(self, text="ACHILLES | Master Prompt Engine", font=("Roboto Medium", 22), text_color="#2CC985")
        self.lbl_header.grid(row=0, column=0, pady=(15, 10), sticky="w", padx=30)

        # 1. SECCIÓN DE IDENTIDAD (Familia)
        self.frm_id = ctk.CTkFrame(self, fg_color="transparent")
        self.frm_id.grid(row=1, column=0, padx=30, pady=5, sticky="ew")
        
        ctk.CTkLabel(self.frm_id, text="ID DE FAMILIA:", font=("Arial", 14, "bold")).pack(side="left", padx=(0, 10))
        self.entry_family = ctk.CTkEntry(self.frm_id, width=300, height=35, placeholder_text="Ejemplo: 8797arg, facturas_v1...", font=("Consolas", 14))
        self.entry_family.pack(side="left", padx=5)
        self.entry_family.bind("<KeyRelease>", self.update_batch_status)

        # 2. ZONA DE CARGA DE ARCHIVOS (Compacta)
        self.frm_upload = ctk.CTkFrame(self, fg_color="#2B2B2B", border_width=1, border_color="#3D3D3D")
        self.frm_upload.grid(row=2, column=0, padx=30, pady=10, sticky="ew")
        self.frm_upload.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.frm_upload, text="CONFIGURACIÓN DE LOTE", font=("Arial", 11, "bold"), text_color="#2CC985").grid(row=0, column=0, columnspan=3, pady=(5, 10))

        self.create_input_row(self.frm_upload, 1, "Documento (PDF/JPG):", "Cargar", "pdf_path", [("Docs", "*.pdf *.jpg")])
        self.create_input_row(self.frm_upload, 2, "Datos Esperados:", "Cargar", "expected_path", [("Data", "*.txt *.json")], allow_edit=True)
        self.create_input_row(self.frm_upload, 3, "Prompt Base (Opcional):", "Cargar", "initial_prompt_path", [("Txt", "*.txt")], allow_edit=True)

        self.btn_add = ctk.CTkButton(self.frm_upload, text="⬇️ VINCULAR Y AGREGAR AL LOTE", command=self.add_case_to_batch, 
                                    fg_color="#333", hover_color="#444", height=32, font=("Arial", 12, "bold"))
        self.btn_add.grid(row=4, column=0, columnspan=4, pady=15, padx=20, sticky="ew")

        # 3. STATUS Y ACCIONES (Fila Horizontal para ahorrar espacio)
        self.frm_actions = ctk.CTkFrame(self, fg_color="transparent")
        self.frm_actions.grid(row=4, column=0, padx=30, pady=5, sticky="ew")

        self.lbl_batch_status = ctk.CTkLabel(self.frm_actions, text="📂 Lote vacío.", font=("Arial", 14, "bold"), text_color="#FFA500")
        self.lbl_batch_status.pack(side="left", padx=5)

        self.btn_reset = ctk.CTkButton(self.frm_actions, text="🗑️ LIMPIAR TODO", command=self.reset_session, 
                                      fg_color="#555", hover_color="#8B0000", width=150, height=35)
        self.btn_reset.pack(side="right", padx=5)

        self.btn_run = ctk.CTkButton(self.frm_actions, text="▶️ INICIAR OPTIMIZACIÓN MAESTRA", command=self.start_batch_process, 
                                    fg_color="#00835D", hover_color="#006648", width=300, height=40, font=("Roboto", 14, "bold"))
        self.btn_run.pack(side="right", padx=20)

        # 4. REGISTRO DE AUDITORÍA (Ocupa el resto de la pantalla)
        ctk.CTkLabel(self, text="REGISTRO DE AUDITORÍA Y PENSAMIENTO DE IA:", font=("Arial", 11, "bold"), text_color="gray").grid(row=6, column=0, padx=30, sticky="w", pady=(15, 5))
        
        self.textbox_log = ctk.CTkTextbox(self, font=("Consolas", 12), text_color="#E0E0E0", fg_color="#121212", border_width=1, border_color="#333")
        self.textbox_log.grid(row=7, column=0, padx=30, pady=(0, 25), sticky="nsew")
        
        sys.stdout = TextRedirector(self.textbox_log)
        sys.stderr = TextRedirector(self.textbox_log)

        self.cleanup_temp_files()

    def reset_session(self):
        if not messagebox.askyesno("Confirmar Limpieza", "¿Seguro que quieres borrar todos los documentos cargados y empezar de cero?"):
            return
        print("\n🧹 Limpiando sesión de trabajo...")
        def force_remove_readonly(func, path, excinfo):
            import stat
            os.chmod(path, stat.S_IWRITE) 
            func(path)
        try:
            if main.DOCS_DIR.exists():
                shutil.rmtree(main.DOCS_DIR, onerror=force_remove_readonly)
            time.sleep(0.5)
            os.makedirs(main.DOCS_DIR, exist_ok=True)
            self.clear_input("pdf_path", self.lbl_pdf_path)
            self.clear_input("expected_path", self.lbl_expected_path)
            self.clear_input("initial_prompt_path", self.lbl_initial_prompt_path)
            self.entry_family.delete(0, 'end')
            self.update_batch_status()
            print("✅ Carpeta de casos vacía y variables reseteadas.")
        except Exception as e:
            print(f"⚠️ Error al limpiar: {e}")

    def create_input_row(self, parent, row, label_text, btn_text, var_name, file_types, allow_edit=False):
        ctk.CTkLabel(parent, text=label_text, font=("Arial", 12)).grid(row=row, column=0, padx=20, pady=5, sticky="w")
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        cmd_load = lambda: self.select_file(var_name, file_types, lbl_val)
        ctk.CTkButton(frame, text=btn_text, command=cmd_load, width=80, height=24).grid(row=0, column=0, padx=(0, 5))

        lbl_val = ctk.CTkLabel(frame, text="...", text_color="gray", anchor="w", font=("Consolas", 11))
        lbl_val.grid(row=0, column=1, padx=5, sticky="ew")
        
        if DRAG_DROP_AVAILABLE:
            def on_drop(event):
                path = event.data.strip('{}')
                setattr(self, var_name, path)
                lbl_val.configure(text=os.path.basename(path), text_color="white")
            lbl_val.drop_target_register(DND_FILES); lbl_val.dnd_bind('<<Drop>>', on_drop)

        if allow_edit:
            cmd_edit = lambda: self.open_editor(var_name, lbl_val)
            ctk.CTkButton(frame, text="✏️", width=28, height=24, fg_color="#444", command=cmd_edit).grid(row=0, column=2, padx=2)

        cmd_clear = lambda: self.clear_input(var_name, lbl_val)
        ctk.CTkButton(frame, text="❌", width=28, height=24, fg_color="#552222", command=cmd_clear).grid(row=0, column=3, padx=2)
        setattr(self, f"lbl_{var_name}", lbl_val)

    def select_file(self, var_name, ftypes, lbl):
        f = filedialog.askopenfilename(filetypes=ftypes)
        if f: 
            setattr(self, var_name, f)
            lbl.configure(text=os.path.basename(f), text_color="white")

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
        fam = main.sanitize_family_id(self.entry_family.get())
        if not fam: self.lbl_batch_status.configure(text="📂 Esperando ID..."); return
        count = len(list(main.DOCS_DIR.glob(f"expected_{fam}_*.txt"))) if main.DOCS_DIR.exists() else 0
        self.lbl_batch_status.configure(text=f"📂 Familia '{fam}': {count} casos listos")
        self.imported_count = count

    def add_case_to_batch(self):
        fam = main.sanitize_family_id(self.entry_family.get())
        pdf = self.pdf_path
        exp = self.expected_path
        if not fam or not pdf or not exp: 
            messagebox.showwarning("Faltan Datos", "Selecciona documento y datos antes de agregar."); return
        try:
            safe_name = Path(pdf).stem.replace(" ", "_").lower()
            case_id = f"{fam}_{safe_name}"
            os.makedirs(main.DOCS_DIR, exist_ok=True)
            shutil.copy(pdf, main.DOCS_DIR / f"{case_id}{Path(pdf).suffix}")
            shutil.copy(exp, main.DOCS_DIR / f"expected_{case_id}.txt")
            print(f"✅ Caso vinculado: {case_id}")
            self.clear_input("pdf_path", self.lbl_pdf_path)
            self.clear_input("expected_path", self.lbl_expected_path)
            self.update_batch_status()
        except Exception as e: messagebox.showerror("Error", str(e))

    def start_batch_process(self):
        fam = main.sanitize_family_id(self.entry_family.get())
        if not fam: messagebox.showerror("Error", "Falta el ID de Familia."); return
        if self.imported_count == 0: 
            if not messagebox.askyesno("¿Buscar?", f"No hay archivos nuevos. ¿Procesar casos existentes de '{fam}'?"): return
        self.btn_run.configure(state="disabled", text="⏳ OPTIMIZANDO...")
        threading.Thread(target=self.run_logic, args=(fam,), daemon=True).start()

    def run_logic(self, family):
        try:
            print(f"\n🚀 INICIANDO PROCESO MAESTRO PARA: {family.upper()}")
            os.makedirs(main.PROMPTS_DIR, exist_ok=True)
            dest_master = main.PROMPTS_DIR / f"MASTER_{family}.txt"
            
            if self.initial_prompt_path:
                try:
                    if os.path.abspath(self.initial_prompt_path) != os.path.abspath(dest_master):
                        shutil.copy(self.initial_prompt_path, dest_master)
                        print(f"📝 Prompt Semilla cargado correctamente.")
                except Exception as e: print(f"⚠️ Nota: {e}")

            result = main.run_family_batch(family)
            
            if result:
                score = result.get('best_avg_score', 0.0)
                tactic = result.get('best_tactic', "")
                original = result.get('original_prompt', "")
                
                # --- 1. RESCATAMOS LA BANDERA DE MANUSCRITO ---
                flag_manuscrito = result.get('has_handwriting', False)
                
                expected_keys = []
                batch_q = result.get('batch_queue', [])
                if batch_q and 'expected_data' in batch_q[0]:
                    expected_keys = list(batch_q[0]['expected_data'].keys())

                base_prompt = original.split("=== ORIGINAL PROMPT ===")[1].strip() if "=== ORIGINAL PROMPT ===" in original else original
                raw_content = f"=== OPTIMIZED TACTIC (Family Version) ===\n{tactic}\n\n=== ORIGINAL PROMPT ===\n{base_prompt}"
                
                # --- 2. PASAMOS LA BANDERA AL AGENTE ---
                final_content = nodes.syntax_enforcer_agent(
                    raw_content, 
                    expected_keys, 
                    has_handwriting=flag_manuscrito  # <--- EL PUENTE APLICADO AQUÍ
                )
                
                print(f"\n✋ VALIDACIÓN FINAL REQUERIDA.")
                if messagebox.askyesno("Resultado Final", f"Entrenamiento completado con {score:.1f}%.\n¿Sobrescribir el Prompt Maestro?"):
                    with open(dest_master, "w", encoding="utf-8") as f: f.write(final_content)
                    print(f"✅ GUARDADO EXITOSO.")
                else: print(f"🚫 Guardado cancelado.")
            else: print("❌ El proceso no generó resultados válidos.")
        except Exception as e: print(f"❌ Error crítico: {e}"); import traceback; traceback.print_exc()
        finally: 
            self.btn_run.configure(state="normal", text="▶️ INICIAR OPTIMIZACIÓN")
            self.update_batch_status()

if __name__ == "__main__":
    # Usar las rutas ya calculadas en main para que coincidan siempre
    if not main.DOCS_DIR.exists(): 
        main.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not main.PROMPTS_DIR.exists(): 
        main.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        
    app = AchillesApp()
    app.mainloop()