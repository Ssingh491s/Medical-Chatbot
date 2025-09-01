import os
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from threading import Thread
from openai import OpenAI
import fitz  # PyMuPDF

# 🔒 Load API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Please set your OPENAI_API_KEY environment variable.")
client = OpenAI(api_key=api_key)

class Chatbot:
    def __init__(self, root):
        self.root = root
        self.root.title("🩺 Medical Chatbot")
        self.root.geometry("600x650")
        self.root.resizable(True, True)

        # Load keywords and greetings from files
        self.allowed_keywords = self.load_list_from_file("medical_keywords.txt")
        self.greetings = self.load_list_from_file("greetings.txt")

        self.setup_ui()

    def load_list_from_file(self, filename):
        """Load keywords or greetings from a text file."""
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return [line.strip().lower() for line in f if line.strip()]
        else:
            print(f"⚠ Warning: {filename} not found.")
            return []

    def setup_ui(self):
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_display = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, state='disabled',
            bg="#f5f5f5", font=('Arial', 11), padx=10, pady=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(control_frame, text="Clear Chat", command=self.clear_chat).pack(side=tk.RIGHT)
        ttk.Button(control_frame, text="Upload Medical Report", command=self.upload_medical_report).pack(side=tk.LEFT, padx=(0, 5))

        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(10, 0))

        self.user_input = tk.Text(
            input_frame, height=4, font=('Arial', 11),
            bg="white", wrap=tk.WORD
        )
        self.user_input.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.user_input.bind("<Return>", self.on_enter_pressed)

        send_btn = ttk.Button(input_frame, text="Send", width=8, command=self.send_message)
        send_btn.pack(side=tk.RIGHT, padx=(5, 0))

    def clear_chat(self):
        self.chat_display.config(state='normal')
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state='disabled')

    def on_enter_pressed(self, event):
        if event.state & 0x0001:  # Shift pressed
            return
        else:
            self.send_message()
            return "break"

    def send_message(self):
        message = self.user_input.get("1.0", tk.END).strip()
        if not message:
            return

        self.update_chat("You", message, is_user=True)
        self.user_input.delete("1.0", tk.END)

        # Check if message is allowed
        if not self.is_allowed_message(message):
            self.update_chat("MedicalBot",
                "I can only answer medical-related questions. Please ask something about health, symptoms, treatments, etc.",
                is_user=False)
            return

        Thread(target=self.get_ai_response, args=(message,), daemon=True).start()

    def is_allowed_message(self, message):
        message_lower = message.lower()
        if any(greet in message_lower for greet in self.greetings):
            return True
        if any(keyword in message_lower for keyword in self.allowed_keywords):
            return True
        return False

    def get_ai_response(self, prompt):
        try:
            chat_completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a medical assistant that only provides information "
                            "and answers related to medical topics, healthcare, symptoms, "
                            "diagnosis, treatments, medicines, and wellness advice. "
                            "If the user asks something unrelated to medical topics, "
                            "politely refuse and remind them you only answer medical questions."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            response = chat_completion.choices[0].message.content.strip()
            self.update_chat("MedicalBot", response, is_user=False)
        except Exception as e:
            self.update_chat("System", f"Error: {str(e)}", is_error=True)

    def upload_medical_report(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("PDF Files", "*.pdf")],
            title="Select Medical Report PDF"
        )
        if not file_path:
            return

        try:
            doc = fitz.open(file_path)
            extracted_text = ""
            for page in doc:
                extracted_text += page.get_text()

            if not extracted_text.strip():
                self.update_chat("System", "No readable text found in PDF.", is_error=True)
                return

            self.update_chat("System", f"📄 Medical Report '{os.path.basename(file_path)}' uploaded. Analyzing...", is_user=False)

            Thread(target=self.analyze_medical_report, args=(extracted_text,), daemon=True).start()

        except Exception as e:
            self.update_chat("System", f"Error reading PDF: {str(e)}", is_error=True)

    def analyze_medical_report(self, report_text):
        try:
            chat_completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional medical assistant. "
                            "Analyze the following medical test report and provide a concise summary, "
                            "highlighting any abnormalities or areas of concern. "
                            "Use layman-friendly language and recommend consulting a doctor if necessary."
                        )
                    },
                    {"role": "user", "content": report_text}
                ],
                temperature=0.3,
                max_tokens=500
            )
            response = chat_completion.choices[0].message.content.strip()
            self.update_chat("MedicalBot", response, is_user=False)

        except Exception as e:
            self.update_chat("System", f"Error analyzing report: {str(e)}", is_error=True)

    def update_chat(self, sender, message, is_user=False, is_error=False, update=False):
        self.chat_display.config(state='normal')

        if not update:
            tag = "user" if is_user else "bot"
            if is_error:
                tag = "error"
            self.chat_display.insert(tk.END, f"{sender}: ", tag)
            self.chat_display.insert(tk.END, "\n", "small")

        if update:
            self.chat_display.delete("end-2l linestart", tk.END)
            self.chat_display.insert(tk.END, f"{sender}: {message}\n\n", "bot")
        else:
            self.chat_display.insert(tk.END, f"{message}\n\n")

        self.chat_display.tag_config("user", foreground="#2c7be5")
        self.chat_display.tag_config("bot", foreground="#00a854")
        self.chat_display.tag_config("error", foreground="#e63757")
        self.chat_display.tag_config("small", font=('Arial', 1))

        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')


if __name__ == "__main__":
    root = tk.Tk()
    app = Chatbot(root)

    style = ttk.Style()
    style.configure("TButton", padding=5)
    style.configure("TCombobox", padding=5)

    root.mainloop()



