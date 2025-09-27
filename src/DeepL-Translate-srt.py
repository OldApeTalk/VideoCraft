import deepl
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import srt
import re

# Function to configure API key
def configure_key():
    def save_key():
        key = entry.get().strip()
        if key:
            with open('DeepL.key', 'w') as f:
                f.write(key)
            messagebox.showinfo("Success", "API key saved successfully!")
            root.destroy()
        else:
            messagebox.showerror("Error", "Please enter a valid API key.")

    root = tk.Tk()
    root.title("DeepL API Key Configuration")
    tk.Label(root, text="Enter your DeepL API Key:").pack(pady=10)
    entry = tk.Entry(root, width=50)
    entry.pack(pady=5)
    tk.Button(root, text="Save", command=save_key).pack(pady=10)
    root.mainloop()

# Check if key file exists
if not os.path.exists('DeepL.key'):
    configure_key()

# Load API key
try:
    with open('DeepL.key', 'r') as f:
        auth_key = f.read().strip()
    translator = deepl.Translator(auth_key)
except Exception as e:
    messagebox.showerror("Error", f"Failed to load API key: {e}")
    exit(1)

# Select SRT file using UI
root = tk.Tk()
root.withdraw()  # Hide the main window
input_file = filedialog.askopenfilename(title="Select SRT File", filetypes=[("SRT files", "*.srt")])
if not input_file:
    messagebox.showinfo("Info", "No file selected. Exiting.")
    exit(0)

# Parse SRT file
try:
    with open(input_file, 'r', encoding='utf-8') as f:
        subs = list(srt.parse(f))
except Exception as e:
    messagebox.showerror("Error", f"Failed to parse SRT file: {e}")
    exit(1)

# Prepare text for translation with numbering for context preservation
texts = []
placeholder = '[NL]'  # Placeholder for newlines
for i, sub in enumerate(subs):
    # Replace newlines in content to preserve multi-line subtitles
    content = sub.content.replace('\n', placeholder)
    texts.append(f"{i+1}. {content}")

# Join into a single string with newlines
full_text = '\n'.join(texts)

# Translate the entire block (assume source is English, target is Chinese; adjust as needed)
try:
    translated = translator.translate_text(
        full_text,
        source_lang='EN',  # Change if needed, or set to None for auto-detect
        target_lang='ZH',
        preserve_formatting=True
    ).text
except Exception as e:
    messagebox.showerror("Error", f"Translation failed: {e}")
    exit(1)

# Extract translated parts using regex
# Match patterns like "1. text" until next number
pattern = re.compile(r'(\d+)\.\s*(.*?)(?=\n\d+\.|$)', re.DOTALL)
matches = pattern.findall(translated)

# Map back to subtitles
translated_subs = {}
for match in matches:
    idx = int(match[0]) - 1
    text = match[1].strip().replace(placeholder, '\n')
    translated_subs[idx] = text

# Check if all subtitles were translated
if len(translated_subs) != len(subs):
    messagebox.showwarning("Warning", "Some subtitles may not have been properly extracted after translation. Check the output.")

# Update subtitles
for i, sub in enumerate(subs):
    if i in translated_subs:
        sub.content = translated_subs[i]
    else:
        # Fallback: keep original if not found
        pass

# Generate output file
output_file = input_file.replace('.srt', '_translated.srt')
try:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(srt.compose(subs))
    messagebox.showinfo("Success", f"Translated SRT saved to: {output_file}")
except Exception as e:
    messagebox.showerror("Error", f"Failed to save output: {e}")