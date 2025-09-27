# VideoCraft

VideoCraft is an open-source Python tool for seamless video processing. It provides a GUI with modular tabs: Download, Transcribe & Translate, and Merge.

## Features
- Download videos from YouTube using `yt-dlp`.
- Transcribe audio to subtitles using `whisper`.
- Translate subtitles into multiple languages using `deep-translator` (DeepL API).
- Merge subtitles with videos using `ffmpeg-python`.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/YourGitHubUsername/VideoCraft.git
   cd VideoCraft
   ```
2. Create and activate a Conda environment:
   ```bash
   conda create -n ai_coding python=3.8
   conda activate ai_coding
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   - Use a mirror if needed: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
4. Ensure FFmpeg is installed and accessible in PATH (download from https://ffmpeg.org).
5. Obtain a DeepL API key from https://www.deepl.com/pro-api and set it in `translate.py`. Note: Free tier includes 50,000 characters/month (each letter, space, or punctuation counts as one character). For optimization, filter non-text lines in subtitles.

## Usage
Run the GUI:
```bash
python src/main.py
```
- Click "Download" to open the download interface.
- Click "Transcribe" to transcribe audio to subtitles.
- Click "Translate" to translate subtitles to a target language.
- Click "Merge" to merge subtitles with a video.

## Development
- Refer to [DESIGN_SPEC.md](DESIGN_SPEC.md) for architecture and requirements.
- Use VSCode with the `ai_coding` Conda environment (select interpreter: `~/anaconda3/envs/ai_coding/bin/python`).
- Create feature branches (e.g., `feature/download-tab`) and submit Pull Requests to `main`.
- Test changes with `pytest tests/` (to be implemented).

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Contact
For questions or inquiries, contact [@YourGitHubUsername](https://github.com/YourGitHubUsername) or email [videocraft.project@gmail.com](mailto:videocraft.project@gmail.com).

## License
VideoCraft is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.