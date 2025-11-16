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
        self.root.geometry("800x700")
        
        # Initialize yt-dlp
        self.ydl_opts = {}
        self.video_list = []  # List of videos from URLs/playlists
        self.selected_videos = []  # Selected videos for download
        
        # Create GUI elements
        self.create_widgets()
        
    def create_widgets(self):
        # URL Input (multi-line for multiple URLs)
        tk.Label(self.root, text="Video URLs (one per line):").pack(pady=5)
        self.url_text = tk.Text(self.root, height=5, width=70)
        self.url_text.pack(pady=5)
        
        # Get Video List Button
        self.get_list_btn = tk.Button(self.root, text="Get Video List", command=self.get_video_list)
        self.get_list_btn.pack(pady=5)
        
        # Video List Display with Checkboxes
        tk.Label(self.root, text="Available Videos:").pack(pady=5)
        self.list_frame = tk.Frame(self.root)
        self.list_frame.pack(pady=5, fill=tk.BOTH, expand=True)
        
        # Scrollbar for list
        self.scrollbar = tk.Scrollbar(self.list_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_listbox = tk.Listbox(self.list_frame, selectmode=tk.MULTIPLE, height=10, width=70, yscrollcommand=self.scrollbar.set)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.video_listbox.yview)
        
        # Select All / Deselect All Buttons
        select_frame = tk.Frame(self.root)
        select_frame.pack(pady=5)
        tk.Button(select_frame, text="Select All", command=self.select_all).grid(row=0, column=0, padx=5)
        tk.Button(select_frame, text="Deselect All", command=self.deselect_all).grid(row=0, column=1, padx=5)
        
        # Format Selection (for all selected videos)
        tk.Label(self.root, text="Video Quality:").pack(pady=5)
        self.quality_combo = ttk.Combobox(self.root, values=["best", "1080p", "720p", "480p", "360p"], state="readonly")
        self.quality_combo.current(0)
        self.quality_combo.pack(pady=5)
        
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
        self.status_text = tk.Text(self.root, height=8, width=70)
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
            
    def select_all(self):
        self.video_listbox.select_set(0, tk.END)
        
    def deselect_all(self):
        self.video_listbox.selection_clear(0, tk.END)
        
    def get_video_list(self):
        urls = self.url_text.get("1.0", tk.END).strip().split('\n')
        urls = [url.strip() for url in urls if url.strip()]
        if not urls:
            messagebox.showerror("Error", "Please enter at least one URL")
            return
            
        self.get_list_btn.config(state="disabled")
        self.log("Fetching video list...")
        self.video_list = []
        self.video_listbox.delete(0, tk.END)
        
        def fetch_list():
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                    'referer': 'https://www.youtube.com/',
                    'extract_flat': True,  # Get playlist info without downloading
                }
                if self.ipv4_var.get():
                    ydl_opts['force_ipv4'] = True
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    for url in urls:
                        info = ydl.extract_info(url, download=False)
                        if 'entries' in info:
                            # It's a playlist
                            for entry in info['entries']:
                                if entry:
                                    self.video_list.append({
                                        'title': entry.get('title', 'Unknown'),
                                        'url': entry.get('url', entry.get('webpage_url', url)),
                                        'duration': entry.get('duration', 0),
                                        'uploader': entry.get('uploader', 'Unknown')
                                    })
                        else:
                            # Single video
                            self.video_list.append({
                                'title': info.get('title', 'Unknown'),
                                'url': info.get('webpage_url', url),
                                'duration': info.get('duration', 0),
                                'uploader': info.get('uploader', 'Unknown')
                            })
                
                self.root.after(0, self.update_video_listbox)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch video list: {str(e)}"))
                self.root.after(0, lambda: self.log(f"Error: {str(e)}"))
                self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
                
        threading.Thread(target=fetch_list, daemon=True).start()
            
    def update_video_listbox(self):
        for video in self.video_list:
            duration_str = f"{video['duration'] // 60}:{video['duration'] % 60:02d}" if video['duration'] else "Unknown"
            display_text = f"{video['title']} - {duration_str} - {video['uploader']}"
            self.video_listbox.insert(tk.END, display_text)
        self.get_list_btn.config(state="normal")
        self.download_btn.config(state="normal")
        self.log(f"Found {len(self.video_list)} videos")
        
    def clear_cache(self):
        self.log("Clearing yt-dlp cache...")
        try:
            subprocess.run(['yt-dlp', '--rm-cache-dir'], check=True)
            self.log("Cache cleared successfully! Try fetching formats again.")
            messagebox.showinfo("Success", "yt-dlp cache cleared. This may fix 403 errors.")
        except Exception as e:
            self.log(f"Error clearing cache: {str(e)}")
            messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")
        
    def start_download(self):
        selected_indices = self.video_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "Please select at least one video to download")
            return
            
        output_dir = self.dir_entry.get().strip()
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
            
        if not os.path.exists(output_dir):
            messagebox.showerror("Error", "Invalid output directory")
            return
            
        self.selected_videos = [self.video_list[i] for i in selected_indices]
        quality = self.quality_combo.get()
        
        self.download_btn.config(state="disabled")
        self.get_list_btn.config(state="disabled")
        self.log(f"Starting download of {len(self.selected_videos)} videos...")
        
        def download():
            try:
                # Check FFmpeg
                try:
                    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.root.after(0, lambda: messagebox.showerror("Error", "FFmpeg not found. Install FFmpeg for video processing."))
                    self.root.after(0, lambda: self.log("Error: FFmpeg not found"))
                    self.root.after(0, lambda: self.download_btn.config(state="normal"))
                    self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
                    return
                
                for video in self.selected_videos:
                    self.log(f"Downloading: {video['title']}")
                    
                    # Map quality to format
                    format_str = {
                        "best": "best[height<=1080]",
                        "1080p": "best[height<=1080]",
                        "720p": "best[height<=720]",
                        "480p": "best[height<=480]",
                        "360p": "best[height<=360]"
                    }.get(quality, "best")
                    
                    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
                    
                    ydl_opts = {
                        'format': f"{format_str}/best",
                        'outtmpl': output_template,
                        'merge_output_format': 'mp4',
                        'postprocessor_args': {'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac']},
                        'progress_hooks': [lambda d, v=video: self.progress_hook(d, v)],
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'referer': 'https://www.youtube.com/',
                    }
                    
                    if self.ipv4_var.get():
                        ydl_opts['force_ipv4'] = True
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(video['url'], download=True)
                        video_file = ydl.prepare_filename(info)
                    
                    self.root.after(0, lambda vf=video_file: self.log(f"Saved: {vf}"))
                    
                    # Extract MP3 if selected
                    if self.mp3_var.get():
                        self.log("Extracting MP3...")
                        mp3_file = os.path.splitext(video_file)[0] + '.mp3'
                        try:
                            subprocess.run([
                                'ffmpeg', '-i', video_file, '-vn', '-acodec', 'mp3',
                                '-ab', '192k', '-y', mp3_file
                            ], check=True, capture_output=True)
                            self.root.after(0, lambda mf=mp3_file: self.log(f"MP3 saved: {mf}"))
                        except subprocess.CalledProcessError as e:
                            self.root.after(0, lambda: self.log(f"MP3 extraction failed: {e.stderr}"))
                
                self.root.after(0, lambda: self.log("All downloads completed!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "All downloads completed!"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Download failed: {str(e)}"))
                self.root.after(0, lambda: self.log(f"Error: {str(e)}"))
                
            self.root.after(0, lambda: self.download_btn.config(state="normal"))
            self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
        
    def progress_hook(self, d, video=None):
        if d['status'] == 'downloading':
            progress = d.get('_percent_str', '0%').replace('%', '')
            video_title = video['title'] if video else 'Video'
            self.log(f"{video_title} - Progress: {progress}%")
        elif d['status'] == 'finished':
            video_title = video['title'] if video else 'Video'
            self.log(f"{video_title} - Download finished, processing...")
        elif 'error' in d['status'].lower():
            video_title = video['title'] if video else 'Video'
            self.log(f"{video_title} - Error: {d.get('info_dict', {}).get('error', 'Unknown')}")

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloader(root)
    root.mainloop()