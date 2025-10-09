import tkinter as tk
from tkinter import filedialog, messagebox
import srt
from datetime import timedelta
import re

def split_subtitle(sub, max_chars, is_chinese=False):
    """
    Split a subtitle into multiple if it exceeds max_chars.
    For English: split on sentences or commas, and avoid splitting words by finding last space/punctuation.
    For Chinese: split on punctuation or fixed length.
    Distribute time proportionally.
    """
    content = sub.content.strip()
    if len(content) <= max_chars:
        return [sub]
    
    new_subs = []
    start = sub.start
    end = sub.end
    total_duration = (end - start).total_seconds()
    
    # Simple semantic split: find natural breaks
    if is_chinese:
        # For Chinese, split on common punctuation
        breaks = [m.start() for m in re.finditer(r'[，。？！；]', content)] + [len(content)]
    else:
        # For English, split on sentence ends or commas
        breaks = [m.start() for m in re.finditer(r'[.?!,]', content)] + [len(content)]
    
    current_pos = 0
    while current_pos < len(content):
        # Aim for max_chars, but find the best split point <= max_chars
        split_pos = current_pos + max_chars
        if split_pos >= len(content):
            split_pos = len(content)
        else:
            # Find candidates from breaks within range
            candidates = [b + 1 for b in breaks if current_pos < b + 1 <= split_pos]
            if candidates:
                split_pos = max(candidates)
            else:
                # No punctuation break: find last space to avoid word split (for English)
                if not is_chinese:
                    last_space = content.rfind(' ', current_pos, split_pos)
                    if last_space > current_pos:
                        split_pos = last_space + 1  # Include the space or cut before it? Better to cut after space for clean trim.
                    # If no space, hard split (rare for English)
                # For Chinese, hard split is fine
        
        part_content = content[current_pos:split_pos].strip()
        if not part_content:
            break
        
        # Calculate time for this part
        part_duration = (len(part_content) / len(content)) * total_duration
        part_end = start + timedelta(seconds=part_duration)
        
        new_sub = srt.Subtitle(
            index=len(new_subs) + 1,  # Temporary index
            start=start,
            end=part_end,
            content=part_content
        )
        new_subs.append(new_sub)
        
        start = part_end
        current_pos = split_pos
    
    # Adjust total end to original end
    if new_subs:
        new_subs[-1].end = end
    
    return new_subs

def process_srt(input_path, output_path, max_chars, is_chinese=False):
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f))
        
        new_subs = []
        for sub in subs:
            new_subs.extend(split_subtitle(sub, max_chars, is_chinese))
        
        # Re-index
        for i, sub in enumerate(new_subs, 1):
            sub.index = i
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt.compose(new_subs))
        
        messagebox.showinfo("Success", f"Processed SRT saved to {output_path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def select_file_and_process(max_chars, is_chinese=False):
    input_path = filedialog.askopenfilename(title="Select SRT File", filetypes=[("SRT files", "*.srt")])
    if not input_path:
        return
    
    output_path = filedialog.asksaveasfilename(title="Save Processed SRT", defaultextension=".srt", filetypes=[("SRT files", "*.srt")])
    if not output_path:
        return
    
    process_srt(input_path, output_path, max_chars, is_chinese)

def custom_process():
    try:
        max_chars = int(entry.get())
        if max_chars <= 0:
            raise ValueError("Max characters must be positive")
        select_file_and_process(max_chars)
    except ValueError as e:
        messagebox.showerror("Invalid Input", str(e))

# GUI Setup
root = tk.Tk()
root.title("SRT Subtitle Splitter")

tk.Label(root, text="Custom Max Characters:").pack(pady=5)
entry = tk.Entry(root)
entry.pack(pady=5)

tk.Button(root, text="Process with Custom Limit", command=custom_process).pack(pady=10)
tk.Button(root, text="Process English (60 chars)", command=lambda: select_file_and_process(60, is_chinese=False)).pack(pady=10)
tk.Button(root, text="Process Chinese (20 chars)", command=lambda: select_file_and_process(20, is_chinese=True)).pack(pady=10)

root.mainloop()