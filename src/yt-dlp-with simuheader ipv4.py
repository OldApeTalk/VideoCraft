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
        self.root.geometry("1200x600")  # Wider window for horizontal layout
        
        # Initialize yt-dlp
        self.ydl_opts = {}
        self.video_list = []  # List of videos from URLs/playlists
        self.selected_videos = []  # Selected videos for download
        
        # Create GUI elements
        self.create_widgets()
        
    def create_widgets(self):
        # Create main frames for left and right panels
        left_frame = tk.Frame(self.root, padx=10, pady=10)
        left_frame.grid(row=0, column=0, sticky="nsew")
        
        right_frame = tk.Frame(self.root, padx=10, pady=10)
        right_frame.grid(row=0, column=1, sticky="nsew")
        
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Left Panel - Input and Selection
        # URL Input (multi-line for multiple URLs)
        tk.Label(left_frame, text="Video URLs (one per line):", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
        self.url_text = tk.Text(left_frame, height=4, width=50, wrap=tk.WORD)
        self.url_text.pack(fill=tk.X, pady=(0,10))
        
        # Get Video List Button
        self.get_list_btn = tk.Button(left_frame, text="Get Video List", command=self.get_video_list, 
                                    bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.get_list_btn.pack(fill=tk.X, pady=(0,10))
        
        # Video List Display with Checkboxes
        tk.Label(left_frame, text="Available Videos:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
        self.list_frame = tk.Frame(left_frame)
        self.list_frame.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        # Scrollbar for list
        self.scrollbar = tk.Scrollbar(self.list_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.video_listbox = tk.Listbox(self.list_frame, selectmode=tk.MULTIPLE, height=12, width=50, 
                                       yscrollcommand=self.scrollbar.set, font=("Arial", 9))
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.video_listbox.yview)
        
        # Select All / Deselect All Buttons
        select_frame = tk.Frame(left_frame)
        select_frame.pack(pady=(0,10))
        tk.Button(select_frame, text="Select All", command=self.select_all, width=12).grid(row=0, column=0, padx=(0,5))
        tk.Button(select_frame, text="Deselect All", command=self.deselect_all, width=12).grid(row=0, column=1)
        
        # Quality and Options
        options_frame = tk.Frame(left_frame)
        options_frame.pack(fill=tk.X, pady=(0,10))
        
        # Video Quality
        tk.Label(options_frame, text="Video Quality:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        self.quality_combo = ttk.Combobox(options_frame, values=["best", "1080p", "720p", "480p", "360p"], 
                                         state="readonly", width=15)
        self.quality_combo.current(0)
        self.quality_combo.grid(row=1, column=0, sticky="w", pady=(0,10))
        
        # MP3 Checkbox
        self.mp3_var = tk.BooleanVar()
        tk.Checkbutton(options_frame, text="Extract MP3", variable=self.mp3_var, font=("Arial", 9)).grid(row=2, column=0, sticky="w")
        
        # Right Panel - Output and Download
        # Output Directory
        tk.Label(right_frame, text="Download Settings", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0,10))
        
        output_frame = tk.Frame(right_frame)
        output_frame.pack(fill=tk.X, pady=(0,20))
        
        tk.Label(output_frame, text="Save to:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        self.dir_entry = tk.Entry(output_frame, width=40, font=("Arial", 9))
        self.dir_entry.grid(row=1, column=0, sticky="ew", pady=(0,5))
        tk.Button(output_frame, text="Browse", command=self.browse_directory, width=10).grid(row=1, column=1, padx=(5,0))
        
        output_frame.grid_columnconfigure(0, weight=1)
        
        # Download Button
        self.download_btn = tk.Button(right_frame, text="Start Download", command=self.start_download, 
                                    state="disabled", bg="#2196F3", fg="white", font=("Arial", 12, "bold"), 
                                    height=2)
        self.download_btn.pack(fill=tk.X, pady=(0,20))
        
        # Progress/Status Display
        tk.Label(right_frame, text="Download Status", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
        self.status_text = tk.Text(right_frame, height=15, width=50, wrap=tk.WORD, font=("Arial", 9))
        self.status_text.pack(fill=tk.BOTH, expand=True)
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
                # First try with extract_flat=False for full metadata
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': False,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                    'referer': 'https://www.youtube.com/',
                    'extract_flat': False,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    for url in urls:
                        try:
                            info = ydl.extract_info(url, download=False)
                            if 'entries' in info:
                                # It's a playlist
                                for entry in info['entries']:
                                    if entry:
                                        self.video_list.append({
                                            'title': entry.get('title', 'Unknown Title'),
                                            'url': entry.get('webpage_url', entry.get('url', url)),
                                            'duration': entry.get('duration', 0),
                                            'uploader': entry.get('uploader', info.get('uploader', 'Unknown')),
                                            'playlist': info.get('title', 'Unknown Playlist')
                                        })
                            else:
                                # Single video
                                self.video_list.append({
                                    'title': info.get('title', 'Unknown Title'),
                                    'url': info.get('webpage_url', url),
                                    'duration': info.get('duration', 0),
                                    'uploader': info.get('uploader', 'Unknown'),
                                    'playlist': None
                                })
                        except Exception as e:
                            # Fallback to extract_flat=True
                            self.log(f"Fallback for URL: {url}")
                            ydl_flat_opts = ydl_opts.copy()
                            ydl_flat_opts['extract_flat'] = True
                            with yt_dlp.YoutubeDL(ydl_flat_opts) as ydl_flat:
                                info = ydl_flat.extract_info(url, download=False)
                                if 'entries' in info:
                                    # It's a playlist
                                    for entry in info['entries']:
                                        if entry:
                                            self.video_list.append({
                                                'title': entry.get('title', f"Video {entry.get('id', 'Unknown')}"),
                                                'url': entry.get('url', url),
                                                'duration': 0,  # Not available in flat mode
                                                'uploader': info.get('uploader', 'Unknown'),
                                                'playlist': info.get('title', 'Unknown Playlist')
                                            })
                                else:
                                    # Single video
                                    self.video_list.append({
                                        'title': info.get('title', 'Unknown Title'),
                                        'url': info.get('webpage_url', url),
                                        'duration': info.get('duration', 0),
                                        'uploader': info.get('uploader', 'Unknown'),
                                        'playlist': None
                                    })
                
                self.root.after(0, self.update_video_listbox)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to fetch video list: {str(e)}"))
                self.root.after(0, lambda: self.log(f"Error: {str(e)}"))
                self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
                
        threading.Thread(target=fetch_list, daemon=True).start()
            
    def update_video_listbox(self):
        for video in self.video_list:
            duration = int(video['duration']) if video['duration'] else 0
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration > 0 else "Unknown"
            if video.get('playlist'):
                display_text = f"[{video['playlist']}] {video['title']} - {duration_str} - {video['uploader']}"
            else:
                display_text = f"{video['title']} - {duration_str} - {video['uploader']}"
            self.video_listbox.insert(tk.END, display_text)
        self.get_list_btn.config(state="normal")
        if self.video_list:
            self.download_btn.config(state="normal")
        self.log(f"Found {len(self.video_list)} videos")
        
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
        self.log("Initializing download thread...")
        
        def download():
            try:
                self.root.after(0, lambda: self.log("Download thread started successfully"))
                self.root.after(0, lambda: self.log("Checking FFmpeg installation..."))
                # Check FFmpeg
                try:
                    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=10)
                    self.root.after(0, lambda: self.log("FFmpeg check passed"))
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                    error_msg = f"FFmpeg not found or not working: {str(e)}"
                    self.root.after(0, lambda: messagebox.showerror("Error", "FFmpeg not found. Install FFmpeg for video processing."))
                    self.root.after(0, lambda: self.log(error_msg))
                    self.root.after(0, lambda: self.download_btn.config(state="normal"))
                    self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
                    return
                
                for i, video in enumerate(self.selected_videos):
                    video_title = video['title']
                    self.root.after(0, lambda vt=video_title: self.log(f"Starting download {i+1}/{len(self.selected_videos)}: {vt}"))
                    
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
                        'progress_hooks': [self.create_progress_hook(video)],
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'referer': 'https://www.youtube.com/',
                        'quiet': False,
                        'no_warnings': False,
                    }
                    
                    try:
                        self.root.after(0, lambda: self.log(f"Initializing yt-dlp for: {video_title}"))
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            self.root.after(0, lambda: self.log(f"Extracting info for: {video_title}"))
                            info = ydl.extract_info(video['url'], download=True)
                            video_file = ydl.prepare_filename(info)
                        
                        self.root.after(0, lambda vf=video_file, vt=video_title: self.log(f"Downloaded: {vt} -> {vf}"))
                        
                        # Extract MP3 if selected
                        if self.mp3_var.get():
                            self.root.after(0, lambda: self.log(f"Extracting MP3 for: {video_title}"))
                            mp3_file = os.path.splitext(video_file)[0] + '.mp3'
                            try:
                                subprocess.run([
                                    'ffmpeg', '-i', video_file, '-vn', '-acodec', 'mp3',
                                    '-ab', '192k', '-y', mp3_file
                                ], check=True, capture_output=True, timeout=60)
                                self.root.after(0, lambda mf=mp3_file: self.log(f"MP3 saved: {mf}"))
                            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                                error_msg = f"MP3 extraction failed for {video_title}: {str(e)}"
                                self.root.after(0, lambda: self.log(error_msg))
                    
                    except Exception as video_error:
                        error_msg = f"Failed to download {video_title}: {str(video_error)}"
                        self.root.after(0, lambda: self.log(error_msg))
                        continue  # Continue with next video
                
                self.root.after(0, lambda: self.log("All downloads completed!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "All downloads completed!"))
                
            except Exception as e:
                error_msg = f"Download process failed: {str(e)}"
                self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                self.root.after(0, lambda: self.log(error_msg))
                
            finally:
                self.root.after(0, lambda: self.download_btn.config(state="normal"))
                self.root.after(0, lambda: self.get_list_btn.config(state="normal"))
        
        # Start the download thread
        self.log("Starting download thread...")
        threading.Thread(target=download, daemon=True).start()
        
    def create_progress_hook(self, video):
        """Create a progress hook function for a specific video"""
        def progress_hook(d):
            if d['status'] == 'downloading':
                progress = d.get('_percent_str', '0%').replace('%', '')
                video_title = video['title']
                self.root.after(0, lambda: self.log(f"{video_title} - Progress: {progress}%"))
            elif d['status'] == 'finished':
                video_title = video['title']
                self.root.after(0, lambda: self.log(f"{video_title} - Download finished, processing..."))
            elif 'error' in d['status'].lower():
                video_title = video['title']
                error_msg = d.get('info_dict', {}).get('error', 'Unknown error')
                self.root.after(0, lambda: self.log(f"{video_title} - Error: {error_msg}"))
        return progress_hook

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloader(root)
    root.mainloop()