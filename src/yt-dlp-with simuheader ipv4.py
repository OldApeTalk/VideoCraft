import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yt_dlp
import os
import threading
import subprocess
from urllib.parse import urlparse

class YouTubeDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader")
        self.root.geometry("600x550")
        
        # Initialize yt-dlp
        self.ydl_opts = {}
        self.formats = []
        
        # Create GUI elements
        self.create_widgets()
        
    def create_widgets(self):
        # URL Input
        tk.Label(self.root, text="Video URL:").pack(pady=5)
        self.url_entry = tk.Entry(self.root, width=60)
        self.url_entry.pack(pady=5)
        
        # Get Formats Button
        self.get_formats_btn = tk.Button(self.root, text="Get Available Formats", command=self.get_formats)
        self.get_formats_btn.pack(pady=5)
        
        # Format Selection
        tk.Label(self.root, text="Available Formats:").pack(pady=5)
        self.format_combo = ttk.Combobox(self.root, width=50, state="readonly")
        self.format_combo.pack(pady=5)
        
        # MP3 Checkbox
        self.mp3_var = tk.BooleanVar()
        tk.Checkbutton(self.root, text="Extract MP3", variable=self.mp3_var).pack(pady=5)
        
        # Force IPv4 Checkbox
        self.ipv4_var = tk.BooleanVar()
        tk.Checkbutton(self.root, text="Force IPv4 (for 403 fix)", variable=self.ipv4_var).pack(pady=5)
        
        # Clear Cache Button
        tk.Button(self.root, text="Clear yt-dlp Cache (for 403 fix)", command=self.clear_cache).pack(pady=5)
        
        # Output Directory
        tk.Label(self.root, text="Save to:").pack(pady=5)
        self.dir_entry = tk.Entry(self.root, width=60)
        self.dir_entry.pack(pady=5)
        tk.Button(self.root, text="Browse", command=self.browse_directory).pack(pady=5)
        
        # Download Button
        self.download_btn = tk.Button(self.root, text="Start Download", command=self.start_download, state="disabled")
        self.download_btn.pack(pady=10)
        
        # Progress/Status Display
        tk.Label(self.root, text="Status:").pack(pady=5)
        self.status_text = tk.Text(self.root, height=8, width=60)
        self.status_text.pack(pady=5)
        self.status_text.config(state="disabled")
        
    def log(self, message):
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
        self.root.update()
        
    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
            
    def clear_cache(self):
        self.log("Clearing yt-dlp cache...")
        try:
            subprocess.run(['yt-dlp', '--rm-cache-dir'], check=True)
            self.log("Cache cleared successfully! Try fetching formats again.")
            messagebox.showinfo("Success", "yt-dlp cache cleared. This may fix 403 errors.")
        except Exception as e:
            self.log(f"Error clearing cache: {str(e)}")
            messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")
            
    def get_formats(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a valid URL")
            return
            
        self.get_formats_btn.config(state="disabled")
        self.log("Fetching available formats...")
        
        def fetch_formats():
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                    'referer': 'https://www.youtube.com/',
                    'verbose': True,
                }
                if self.ipv4_var.get():
                    ydl_opts['force_ipv4'] = True
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    self.formats = [f for f in info.get('formats', []) if f.get('vcodec') != 'none']
                    format_strings = [f"{f.get('resolution', 'unknown')} - {f.get('ext', 'unknown')} - "
                                    f"{'Audio' if f.get('acodec') != 'none' else 'No Audio'}"
                                    for f in self.formats]
                    
                    self.root.after(0, lambda: self.update_format_combo(format_strings))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch formats: {str(e)}\nTry clearing cache or enabling IPv4."))
                self.root.after(0, lambda: self.log(f"Error: {str(e)}"))
                self.root.after(0, lambda: self.get_formats_btn.config(state="normal"))
                
        threading.Thread(target=fetch_formats, daemon=True).start()
        
    def update_format_combo(self, format_strings):
        self.format_combo['values'] = format_strings
        if format_strings:
            self.format_combo.current(0)
            self.download_btn.config(state="normal")
        self.get_formats_btn.config(state="normal")
        self.log("Formats loaded successfully")
        
    def start_download(self):
        url = self.url_entry.get().strip()
        output_dir = self.dir_entry.get().strip()
        if not url or not output_dir:
            messagebox.showerror("Error", "Please provide both URL and output directory")
            return
            
        if not os.path.exists(output_dir):
            messagebox.showerror("Error", "Invalid output directory")
            return
            
        self.download_btn.config(state="disabled")
        self.get_formats_btn.config(state="disabled")
        self.log("Starting download...")
        
        def download():
            try:
                selected_format_idx = self.format_combo.current()
                if selected_format_idx < 0 or not self.formats:
                    raise ValueError("No format selected")
                    
                format_id = self.formats[selected_format_idx]['format_id']
                has_audio = self.formats[selected_format_idx].get('acodec') != 'none'
                
                # Prepare output filename
                parsed_url = urlparse(url)
                video_id = parsed_url.path.split('/')[-1]
                output_template = os.path.join(output_dir, f"{video_id}_%(title)s.%(ext)s")
                
                # Check if FFmpeg is available
                try:
                    ffmpeg_version = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                    if 'aac' not in ffmpeg_version.stdout.decode():
                        raise ValueError("FFmpeg lacks AAC encoder support")
                except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
                    self.root.after(0, lambda: messagebox.showerror("Error", "FFmpeg not found or lacks AAC support. Install full FFmpeg for audio merging/extraction."))
                    self.root.after(0, lambda: self.log("Error: FFmpeg issue - check installation"))
                    self.root.after(0, lambda: self.download_btn.config(state="normal"))
                    self.root.after(0, lambda: self.get_formats_btn.config(state="normal"))
                    return
                
                # Download options with headers and IPv4
                self.ydl_opts = {
                    'format': f"{format_id}+bestaudio/best" if not has_audio else format_id,
                    'outtmpl': output_template,
                    'merge_output_format': 'mp4',
                    'postprocessor_args': {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental']},
                    'progress_hooks': [self.progress_hook],
                    'verbose': True,
                    'no_warnings': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                    'referer': 'https://www.youtube.com/',
                }
                
                if self.ipv4_var.get():
                    self.ydl_opts['force_ipv4'] = True
                    self.log("Forcing IPv4 connection...")
                
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_file = ydl.prepare_filename(info)
                
                self.root.after(0, lambda: self.log(f"Video saved as: {video_file} (with AAC audio for compatibility)"))
                
                # Extract MP3 if selected
                if self.mp3_var.get():
                    self.log("Extracting MP3...")
                    mp3_file = os.path.splitext(video_file)[0] + '.mp3'
                    try:
                        subprocess.run([
                            'ffmpeg', '-i', video_file, '-vn', '-acodec', 'mp3',
                            '-ab', '192k', '-y', mp3_file
                        ], check=True, capture_output=True, text=True)
                        self.root.after(0, lambda: self.log(f"MP3 saved as: {mp3_file}"))
                    except subprocess.CalledProcessError as e:
                        error_msg = f"MP3 extraction failed: {e.stderr}"
                        self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                        self.root.after(0, lambda: self.log(error_msg))
                
                self.root.after(0, lambda: self.log("Download completed successfully!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download completed!"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {str(e)}\nTry updating yt-dlp, clearing cache, or enabling IPv4."))
                self.root.after(0, lambda: self.log(f"Error: {str(e)}"))
                
            self.root.after(0, lambda: self.download_btn.config(state="normal"))
            self.root.after(0, lambda: self.get_formats_btn.config(state="normal"))
            
        threading.Thread(target=download, daemon=True).start()
        
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            progress = d.get('_percent_str', '0%').replace('%', '')
            self.log(f"Progress: {progress}%")
        elif d['status'] == 'finished':
            self.log("Download finished, processing...")
        elif d['status'] == 'merging':
            self.log("Merging video and audio (transcoding for compatibility)...")
        elif 'error' in d['status'].lower():
            self.log(f"Error in progress: {d.get('info_dict', {}).get('error', 'Unknown')}")

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloader(root)
    root.mainloop()