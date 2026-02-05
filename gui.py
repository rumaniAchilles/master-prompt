import customtkinter as ctk
import threading
import sys
import os
import shutil
import time
from tkinter import filedialog, messagebox
import main 
import nodes 
import detective 

# Intentamos importar Drag & Drop. Si falla, usamos la ventana normal.
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

# --- CONFIGURACIÓN DE IDENTIDAD CORPORATIVA ACHILLES ---
ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("green") 

class TextRedirector(object):
    """Redirecciona la salida de consola al panel de auditoría."""
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
    """Ventana emergente para editar texto (El Lapicito)"""
    def __init__(self, parent, title, initial_text=""):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x600")
        
        # --- MEJORA: SIEMPRE ADELANTE ---
        self.attributes("-topmost", True)
        
        self.result_path = None
        self.parent = parent
        
        # Fuente Consolas para ver la estructura JSON/Prompt claramente
        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 14), wrap="none")
        self.textbox.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        
        if initial_text:
            self.textbox.insert("0.0", initial_text)
            
        # Botonera
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        btn_save = ctk.CTkButton(btn_frame, text="💾 Guardar Cambios", command=self.save_content, fg_color="#00835D", width=150)
        btn_save.pack(side="left", padx=10)
        
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancelar", command=self.destroy, fg_color="#555", width=100)
        btn_cancel.pack(side="left", padx=10)
        
        self.lift() 
        self.focus_force()

    def save_content(self):
        content = self.textbox.get("0.0", "end").strip()
        if not content:
            self.destroy()
            return
            
        # Guardamos en un temporal .txt conservando estructura
        filename = f"temp_editor_{int(time.time())}.txt"
        path = os.path.abspath(os.path.join(main.DOCS_DIR, filename))
        os.makedirs(main.DOCS_DIR, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
        self.result_path = path
        self.destroy()

class AchillesApp(AchillesBase):
    def __init__(self):
        super().__init__()

        self.title("Achilles | Data Insight Automation (Pro)")
        self.geometry("1100x950")
        
        # Icono (opcional)
        # try: self.iconbitmap("achilles.ico")
        # except: pass

        # --- VARIABLES DE ESTADO ---
        self.pdf_path = None
        self.expected_path = None
        self.initial_prompt_path = None 
        self.last_family_id = "" 

        # --- GRID LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(9, weight=1)

        # 0. HEADER
        self.lbl_header = ctk.CTkLabel(
            self, text="ACHILLES | Generador de Prompts Maestros", 
            font=("Roboto Medium", 20), text_color="#2CC985"
        )
        self.lbl_header.grid(row=0, column=0, columnspan=3, pady=(20, 20), sticky="ew")

        # 1. API KEY
        self.lbl_api = ctk.CTkLabel(self, text="Credencial (API Key):", font=("Arial", 12, "bold"))
        self.lbl_api.grid(row=1, column=0, padx=30, pady=10, sticky="w")
        self.entry_api = ctk.CTkEntry(self, placeholder_text="Ingrese su llave...", width=400, show="●")
        self.entry_api.grid(row=1, column=1, columnspan=2, padx=30, pady=10, sticky="ew")

        # 2. FAMILIA
        self.lbl_family = ctk.CTkLabel(self, text="ID Categoría:", font=("Arial", 12, "bold"))
        self.lbl_family.grid(row=2, column=0, padx=30, pady=10, sticky="w")
        self.entry_family = ctk.CTkEntry(self, placeholder_text="Ej: certificado_iso9001")
        self.entry_family.grid(row=2, column=1, columnspan=2, padx=30, pady=10, sticky="ew")
        
        self.entry_family.bind("<FocusOut>", self.check_family_change)

        # --- GENERADOR DE INPUTS ---
        
        # 3. DOCUMENTO FUENTE
        self.create_input_row(
            row=3, label_text="📂 Documento Fuente:", 
            btn_text="Cargar PDF/Img", 
            var_name="pdf_path", file_types=[("Docs", "*.pdf *.jpg *.png")],
            allow_edit=False
        )

        # 4. RESPUESTA ESPERADA
        self.create_input_row(
            row=4, label_text="📊 Respuesta Esperada:", 
            btn_text="Cargar JSON/TXT", 
            var_name="expected_path", file_types=[("Data", "*.txt *.json")],
            allow_edit=True 
        )

        # 5. PROMPT PREVIO
        self.create_input_row(
            row=5, label_text="📝 Prompt Existente:", 
            btn_text="Cargar Prompt", 
            var_name="initial_prompt_path", file_types=[("Txt", "*.txt")],
            allow_edit=True 
        )

        # 6. BOTÓN RUN
        self.btn_run = ctk.CTkButton(
            self, text="INICIAR PROCESO DE VALIDACIÓN", 
            command=self.start_process, fg_color="#00835D", hover_color="#006648",
            height=50, font=("Roboto", 14, "bold")
        )
        self.btn_run.grid(row=6, column=0, columnspan=3, padx=30, pady=30, sticky="ew")

        # 7. LOGS
        self.lbl_log = ctk.CTkLabel(self, text="Registro de Auditoría:")
        self.lbl_log.grid(row=7, column=0, padx=30, sticky="nw")
        
        self.textbox_log = ctk.CTkTextbox(self, font=("Consolas", 11), text_color="#E0E0E0", fg_color="#1A1A1A")
        self.textbox_log.grid(row=8, column=0, columnspan=3, padx=30, pady=(0, 20), sticky="nsew")
        
        sys.stdout = TextRedirector(self.textbox_log)
        sys.stderr = TextRedirector(self.textbox_log)

    def create_input_row(self, row, label_text, btn_text, var_name, file_types, allow_edit=False):
        """Helper para crear filas de input consistentes."""
        lbl = ctk.CTkLabel(self, text=label_text, font=("Arial", 12, "bold"))
        lbl.grid(row=row, column=0, padx=30, pady=10, sticky="w")

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=1, columnspan=2, padx=30, pady=10, sticky="ew")
        frame.grid_columnconfigure(1, weight=1) 

        cmd_load = lambda: self.select_file(var_name, file_types, lbl_val)
        btn_load = ctk.CTkButton(frame, text=btn_text, command=cmd_load, width=120)
        btn_load.grid(row=0, column=0, padx=(0, 10), sticky="w")

        lbl_val = ctk.CTkLabel(frame, text="Arrastre archivo aquí o cargue...", text_color="gray", anchor="w")
        lbl_val.grid(row=0, column=1, padx=5, sticky="ew")
        
        # DRAG & DROP
        if DRAG_DROP_AVAILABLE:
            def on_drop(event):
                path = event.data.strip('{}') 
                setattr(self, var_name, path)
                lbl_val.configure(text=os.path.basename(path), text_color="white")
            lbl_val.drop_target_register(DND_FILES)
            lbl_val.dnd_bind('<<Drop>>', on_drop)
            btn_load.drop_target_register(DND_FILES)
            btn_load.dnd_bind('<<Drop>>', on_drop)

        # Botón EDITAR (Lápiz) ✏️
        if allow_edit:
            cmd_edit = lambda: self.open_editor(var_name, lbl_val)
            btn_edit = ctk.CTkButton(frame, text="✏️", width=30, fg_color="#444", hover_color="#666", command=cmd_edit)
            btn_edit.grid(row=0, column=2, padx=5, sticky="e")

        # Botón BORRAR (X) ❌
        cmd_clear = lambda: self.clear_input(var_name, lbl_val)
        btn_clear = ctk.CTkButton(frame, text="❌", width=30, fg_color="#C0392B", hover_color="#E74C3C", command=cmd_clear)
        btn_clear.grid(row=0, column=3, padx=(5, 0), sticky="e")

        setattr(self, f"lbl_{var_name}", lbl_val)

    # --- LÓGICA DE INTERFAZ ---
    
    def check_family_change(self, event):
        current_fam = self.entry_family.get().strip()
        if self.last_family_id and current_fam != self.last_family_id:
            print(f"🔄 Cambio de categoría detectado. Reiniciando inputs...")
            self.clear_input("initial_prompt_path", self.lbl_initial_prompt_path)
        self.last_family_id = current_fam

    def select_file(self, var_name, file_types, label_widget):
        f = filedialog.askopenfilename(filetypes=file_types)
        if f:
            setattr(self, var_name, f)
            label_widget.configure(text=os.path.basename(f), text_color="white")

    def clear_input(self, var_name, label_widget):
        setattr(self, var_name, None)
        default_text = "Arrastre archivo aquí o cargue..."
        if var_name == "initial_prompt_path": default_text = "Automático (Modo Detective)"
        label_widget.configure(text=default_text, text_color="gray")

    def open_editor(self, var_name, label_widget):
        current_val = getattr(self, var_name)
        initial_text = ""
        
        window_title = "Editor de Reglas / Texto"
        if var_name == "expected_path": window_title = "Editor de Datos de Validación (Ground Truth)"
        elif var_name == "initial_prompt_path": window_title = "Editor de Protocolo (Prompt)"

        if current_val and os.path.exists(current_val):
            try:
                with open(current_val, "r", encoding="utf-8") as f:
                    initial_text = f.read()
            except: pass
            
        dialog = TextEditorDialog(self, title=window_title, initial_text=initial_text)
        
        # LÓGICA DE ESPERA BLOQUEANTE (RESTAURADA):
        # Esto pausa la app principal hasta que cierres el editor.
        # Al pausarla, impide que abras más ventanas (solucionando el problema de múltiples clicks).
        # Y asegura que el código de abajo no se ejecute hasta que haya un resultado.
        self.wait_window(dialog)
        
        if dialog.result_path:
            setattr(self, var_name, dialog.result_path)
            label_widget.configure(text="[Contenido Editado Manualmente]", text_color="#FFA500")

    # --- LÓGICA DE PROCESO ---

    def start_process(self):
        api = self.entry_api.get().strip()
        fam = self.entry_family.get().strip()
        
        if not api or not fam or not self.pdf_path or not self.expected_path:
            messagebox.showwarning("Faltan Datos", "Complete API, Familia, PDF y Datos de Validación.")
            return

        self.btn_run.configure(state="disabled", text="⏳ Ejecutando...")
        threading.Thread(target=self.run_logic, args=(api, fam), daemon=True).start()

    def run_logic(self, api_key, family):
        try:
            print(f"\n{'='*60}")
            print(f"🔐 ACHILLES | PROTOCOLO: {family.upper()}")
            print(f"{'='*60}")
            
            nodes.client.api_key = api_key
            detective.client.api_key = api_key
            os.makedirs(main.DOCS_DIR, exist_ok=True)
            os.makedirs(main.PROMPTS_DIR, exist_ok=True)
            
            case_id = family 
            shutil.copy(self.pdf_path, main.DOCS_DIR / f"{case_id}{os.path.splitext(self.pdf_path)[1]}")
            shutil.copy(self.expected_path, main.DOCS_DIR / f"expected_{case_id}.txt")

            dest_master = main.PROMPTS_DIR / f"MASTER_{family}.txt"
            is_new_protocol = True

            if self.initial_prompt_path:
                print(f"📋 Protocolo base seleccionado.")
                src_abs = os.path.abspath(self.initial_prompt_path)
                dst_abs = os.path.abspath(dest_master)
                
                if src_abs != dst_abs:
                    shutil.copy(self.initial_prompt_path, dest_master)
                    print("   -> Copiado al directorio de trabajo.")
                else:
                    print("   -> El archivo seleccionado YA ES el maestro actual. Se iterará sobre él.")
                
                is_new_protocol = False
                
            elif os.path.exists(dest_master):
                print(f"📂 Protocolo existente detectado.")
                is_new_protocol = False
            else:
                print(f"🔍 Modo Detective Activado.")

            result_data = main.run_case(case_id, family)
            
            if not result_data:
                print("❌ Error en motor.")
                return

            final_score = result_data['final_score']
            best_tactic = result_data['best_tactic']
            original_prompt = result_data['original_prompt_base']
            
            print(f"\n✋ VALIDACIÓN REQUERIDA.")
            should_save = False
            
            if is_new_protocol:
                if final_score > 0:
                    should_save = messagebox.askyesno("Nuevo Protocolo", f"Score: {final_score:.1f}%\n¿Certificar este nuevo protocolo?")
            else:
                msg = f"Score actual: {final_score:.1f}%"
                if final_score >= 98: msg += "\n(¡Resultado Perfecto!)"
                should_save = messagebox.askyesno("Actualizar Protocolo", f"{msg}\n¿Sobrescribir el protocolo maestro?")

            if should_save:
                self.save_master_file(family, original_prompt, best_tactic, final_score)
            else:
                print("🚫 Cambios descartados.")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback; traceback.print_exc()
        finally:
            self.btn_run.configure(state="normal", text="REINICIAR PROCESO")

    def save_master_file(self, family, original_prompt, winning_tactic, score):
        try:
            separator = "=== OPTIMIZED TACTIC (Family Version) ==="
            if "=== ORIGINAL PROMPT ===" in original_prompt:
                 base_prompt = original_prompt.split("=== ORIGINAL PROMPT ===")[1].strip()
            else:
                 base_prompt = original_prompt.strip()

            final_content = (
                f"{separator}\n"
                f"{winning_tactic}\n\n"
                f"=== ORIGINAL PROMPT ===\n"
                f"{base_prompt}"
            )
            
            path = main.PROMPTS_DIR / f"MASTER_{family}.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write(final_content)
            
            print(f"\n✅ GUARDADO. Score: {score:.1f}%")
            messagebox.showinfo("Éxito", "Protocolo actualizado.")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    if not os.path.exists("casos_docs"): os.makedirs("casos_docs")
    if not os.path.exists("prompt_textos"): os.makedirs("prompt_textos")
    app = AchillesApp()
    app.mainloop()