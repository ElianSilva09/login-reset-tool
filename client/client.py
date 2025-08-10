import tkinter as tk
from tkinter import messagebox
import requests
import subprocess
import os
import sys

# Configura caminhos para DLLs (se necessário)
if hasattr(sys, '_MEIPASS'):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ['PATH']
    os.chdir(sys._MEIPASS)
else:
    lib_path = os.path.join(os.path.dirname(__file__), "libraries")
    if os.path.exists(lib_path):
        os.environ['PATH'] = lib_path + os.pathsep + os.environ['PATH']
# Configurações (ATUALIZE COM SUA URL DO RENDER)
API_URL = "https://login-reset-tool.onrender.com"  # Substitua pela sua URL real
RESET_PATH = "reset_tool.exe"  # Nome do seu executável original

class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Login - Reset Tool")
        self.root.geometry("300x200")
        
        # Elementos da interface
        tk.Label(root, text="Usuário:").pack(pady=5)
        self.entry_usuario = tk.Entry(root)
        self.entry_usuario.pack(pady=5)
        
        tk.Label(root, text="Senha:").pack(pady=5)
        self.entry_senha = tk.Entry(root, show="*")
        self.entry_senha.pack(pady=5)
        
        tk.Button(root, text="Login", command=self.login).pack(pady=10)
        tk.Button(root, text="Cadastrar", command=self.cadastrar).pack(pady=5)
        
    def abrir_reset(self):
        """Abre o programa original de reset"""
        try:
            if os.path.exists(RESET_PATH):
                subprocess.Popen(RESET_PATH)
                self.root.destroy()  # Fecha a janela de login
            else:
                messagebox.showerror("Erro", f"Arquivo {RESET_PATH} não encontrado!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao abrir o programa: {e}")

    def cadastrar(self):
        """Cadastra novo usuário via API"""
        usuario = self.entry_usuario.get()
        senha = self.entry_senha.get()
        
        if not usuario or not senha:
            messagebox.showerror("Erro", "Usuário e senha são obrigatórios!")
            return
            
        try:
            response = requests.post(
                f"{API_URL}/api/cadastrar",
                json={"usuario": usuario, "senha": senha}
            )
            
            if response.status_code == 200:
                messagebox.showinfo("Sucesso", "Usuário cadastrado com sucesso!")
            else:
                error_msg = response.json().get("message", "Erro desconhecido")
                messagebox.showerror("Erro", error_msg)
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro", f"Falha na conexão: {e}")

    def login(self):
        """Faz login via API"""
        usuario = self.entry_usuario.get()
        senha = self.entry_senha.get()
        
        if not usuario or not senha:
            messagebox.showerror("Erro", "Usuário e senha são obrigatórios!")
            return
            
        try:
            response = requests.post(
                f"{API_URL}/api/login",
                json={"usuario": usuario, "senha": senha}
            )
            data = response.json()
            
            if response.status_code == 200:
                self.abrir_reset()
            elif data.get("expirada"):
                messagebox.showerror(
                    "Acesso Expirado", 
                    f"Renove sua assinatura!\nContato: seuemail@exemplo.com"
                )
            else:
                messagebox.showerror("Erro", data.get("message", "Falha no login"))
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro", f"Falha na conexão: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LoginApp(root)
    root.mainloop()