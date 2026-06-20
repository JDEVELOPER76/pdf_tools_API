# gui_launcher_custom.py
import customtkinter as ctk
from tkinter import scrolledtext
import socket
import uvicorn
import threading
import webbrowser
import os
import sys
import logging

from server import app


def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


icon = get_resource_path("icono.ico")


class ConsoleRedirector:
    """Redirige stdout/stderr a un widget Text con manejo de estado"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
    
    def write(self, message):
        try:
            # ✅ Habilitar temporalmente para escribir
            self.text_widget.configure(state='normal')
            
            # Insertar el mensaje
            self.text_widget.insert("end", message)
            self.text_widget.see("end")
            
            # ✅ Volver a deshabilitar
            self.text_widget.configure(state='disabled')
            
        except Exception as e:
            # Si falla, escribir en la consola original
            print(f"Error al escribir en consola: {e}", file=self.original_stdout)
    
    def flush(self):
        pass


class PDFToolsLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PDF Tools Suite - Launcher")
        self.geometry("1000x600")
        try:
            self.iconbitmap(icon)
        except:
            pass
        
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        self.mode_var = ctk.StringVar(value="local")
        self.port_var = ctk.StringVar(value="8000")
        self.ip_var = ctk.StringVar(value="127.0.0.1")
        self.server_thread = None
        self.server_running = False
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.uvicorn_server = None
        self.console_redirector = None
        
        self.setup_ui()
        self.update_ip()
        
        # ✅ Redirigir la consola DESPUÉS de crear el widget
        self.redirect_console()
        
        self.setup_logging()
        
        print("=" * 60)
        print("PDF Tools Suite - Servidor")
        print("=" * 60)
        print("Consola lista para mostrar logs")
        print("=" * 60)
    
    def setup_logging(self):
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    
    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        top_frame = ctk.CTkFrame(self.main_frame)
        top_frame.pack(fill="x", pady=(0, 10))
        
        title = ctk.CTkLabel(
            top_frame,
            text="PDF Tools Suite",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left", padx=(10, 20))
        
        mode_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        mode_frame.pack(side="left", padx=10)
        
        ctk.CTkLabel(mode_frame, text="Modo:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        
        local_radio = ctk.CTkRadioButton(
            mode_frame,
            text="LOCAL",
            variable=self.mode_var,
            value="local",
            command=self.update_ip,
            font=ctk.CTkFont(size=12)
        )
        local_radio.pack(side="left", padx=5)
        
        lan_radio = ctk.CTkRadioButton(
            mode_frame,
            text="LAN",
            variable=self.mode_var,
            value="lan",
            command=self.update_ip,
            font=ctk.CTkFont(size=12)
        )
        lan_radio.pack(side="left", padx=5)
        
        port_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        port_frame.pack(side="left", padx=10)
        
        ctk.CTkLabel(port_frame, text="Puerto:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        
        port_entry = ctk.CTkEntry(
            port_frame,
            textvariable=self.port_var,
            width=80,
            font=ctk.CTkFont(size=12)
        )
        port_entry.pack(side="left")
        
        btn_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)
        
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="Iniciar servidor",
            command=self.start_server,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#047857"
        )
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="Detener servidor",
            command=self.stop_server,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#b91c1c",
            hover_color="#7f1d1d",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        self.open_btn = ctk.CTkButton(
            btn_frame,
            text="Abrir navegador",
            command=self.open_browser,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1e40af",
            hover_color="#1e3a8a",
            state="disabled"
        )
        self.open_btn.pack(side="left", padx=5)
        
        clear_btn = ctk.CTkButton(
            btn_frame,
            text="Limpiar consola",
            command=self.clear_console,
            height=35,
            font=ctk.CTkFont(size=13),
            fg_color="#6b7280",
            hover_color="#4b5563"
        )
        clear_btn.pack(side="left", padx=5)
        
        info_frame = ctk.CTkFrame(self.main_frame)
        info_frame.pack(fill="x", pady=(0, 5))
        
        ip_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        ip_row.pack(side="left", padx=10)
        ctk.CTkLabel(ip_row, text="IP Local:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(ip_row, textvariable=self.ip_var, font=ctk.CTkFont(family="Consolas", size=12)).pack(side="left")
        
        url_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        url_row.pack(side="left", padx=20)
        ctk.CTkLabel(url_row, text="URL:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.url_label = ctk.CTkLabel(
            url_row,
            text="http://127.0.0.1:8000",
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.url_label.pack(side="left")
        
        status_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        status_row.pack(side="right", padx=10)
        ctk.CTkLabel(status_row, text="Estado:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        self.status_label = ctk.CTkLabel(
            status_row,
            text="Servidor detenido",
            font=ctk.CTkFont(size=13)
        )
        self.status_label.pack(side="left")
        
        console_frame = ctk.CTkFrame(self.main_frame)
        console_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        ctk.CTkLabel(
            console_frame,
            text="Consola de logs",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=5, pady=(5, 5))
        
        # ✅ CREAR LA CONSOLA
        self.console = scrolledtext.ScrolledText(
            console_frame,
            wrap='word',
            font=('Consolas', 10),
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white',
            relief='flat',
            height=15
        )
        self.console.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # ✅ NO DESHABILITAR AQUÍ - El redirector manejará el estado
        # self.console.configure(state='disabled')  # <-- ELIMINAR ESTA LÍNEA
    
    def redirect_console(self):
        """Redirige stdout y stderr a la consola"""
        # ✅ Crear el redirector con el widget
        self.console_redirector = ConsoleRedirector(self.console)
        sys.stdout = self.console_redirector
        sys.stderr = self.console_redirector
        
        # ✅ Deshabilitar la consola (el redirector la habilita temporalmente)
        self.console.configure(state='disabled')
    
    def restore_console(self):
        """Restaura stdout y stderr originales"""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
    
    def clear_console(self):
        """Limpia la consola"""
        # ✅ Habilitar temporalmente para limpiar
        self.console.configure(state='normal')
        self.console.delete("1.0", "end")
        # ✅ Volver a deshabilitar
        self.console.configure(state='disabled')
        print("Consola limpiada")
    
    def update_ip(self):
        if self.mode_var.get() == "local":
            ip = "127.0.0.1"
        else:
            ip = self.get_local_ip()
        
        self.ip_var.set(ip)
        port = self.port_var.get().strip() or "8000"
        self.url_label.configure(text=f"http://{ip}:{port}")
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def start_server(self):
        if self.server_running:
            return
        
        try:
            port = int(self.port_var.get().strip() or "8000")
            if port < 1 or port > 65535:
                raise ValueError("Puerto fuera de rango")
        except ValueError as e:
            self.show_error(f"Error: {str(e)}")
            return
        
        mode = self.mode_var.get()
        host = "127.0.0.1" if mode == "local" else "0.0.0.0"
        ip = "127.0.0.1" if mode == "local" else self.get_local_ip()
        
        print("-" * 60)
        print(f"Iniciando servidor en {ip}:{port}")
        print(f"Modo: {mode.upper()}")
        print("-" * 60)
        
        self.status_label.configure(text=f"Iniciando servidor en {ip}:{port}...")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        
        self.server_running = True
        self.server_thread = threading.Thread(
            target=self._run_server,
            args=(host, port),
            daemon=True
        )
        self.server_thread.start()
        
        self.after(1500, lambda: self._update_status_after_start(ip, port))
    
    def _run_server(self, host, port):
        """Ejecuta el servidor Uvicorn."""
        try:
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                reload=False,
                log_level="info",
                log_config=None
            )
            self.uvicorn_server = uvicorn.Server(config)
            self.uvicorn_server.run()
            
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda msg=error_msg: self._show_error(msg))
    
    def _update_status_after_start(self, ip, port):
        if self.server_running:
            self.status_label.configure(
                text=f"Servidor activo en http://{ip}:{port}"
            )
            self.open_btn.configure(state="normal")
            print(f"Servidor iniciado correctamente en http://{ip}:{port}")
    
    def _show_error(self, message):
        self.server_running = False
        self.status_label.configure(text="Error al iniciar")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        print(f"ERROR: {message}")
        self.show_error(f"Error al iniciar el servidor:\n\n{message}")
    
    def stop_server(self):
        """Detiene el servidor SIN cerrar la app."""
        if not self.server_running:
            return
        
        print("-" * 60)
        print("Deteniendo servidor...")
        print("-" * 60)
        
        self.server_running = False
        self.status_label.configure(text="Deteniendo servidor...")
        self.stop_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        
        if hasattr(self, 'uvicorn_server') and self.uvicorn_server:
            try:
                self.uvicorn_server.should_exit = True
                print("Servidor detenido correctamente")
            except Exception as e:
                print(f"Error al detener: {e}")
        else:
            print("No se pudo detener el servidor correctamente")
        
        self.after(2000, self._reset_ui)
        print("=" * 60)
    
    def _reset_ui(self):
        """Restablece la interfaz después de detener el servidor."""
        if not self.server_running:
            self.status_label.configure(text="Servidor detenido")
            self.start_btn.configure(state="normal")
    
    def open_browser(self):
        url = self.url_label.cget("text")
        webbrowser.open(url)
        print(f"Navegador abierto: {url}")
    
    def show_error(self, message):
        import tkinter.messagebox as mb
        mb.showerror("Error", message)
    
    def on_closing(self):
        """Maneja el cierre de la aplicación."""
        if self.server_running:
            self.stop_server()
        
        self.restore_console()
        self.destroy()


if __name__ == "__main__":
    appx = PDFToolsLauncher()
    appx.protocol("WM_DELETE_WINDOW", appx.on_closing)
    appx.mainloop()