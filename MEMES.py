import os, random, time, sys, requests
sys.stdout.reconfigure(encoding='utf-8')
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# ────────────────────────────────────────────────
#  SETTINGS
# ────────────────────────────────────────────────
OUTPUT_DIR = "meme_videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
OUTPUT_SIZE = (1080, 1080)
MUSIC_FILE = "background.mp3"  # put a royalty-free meme bg track beside this script
POST_INTERVAL = 2 * 60 * 60  # 3 hours
REDDIT_SUBS = ["memes", "funny", "dankmemes", "MemeEconomy", "wholesomememes"]

# ────────────────────────────────────────────────
#  AUTHENTICATE WITH YOUTUBE
# ────────────────────────────────────────────────
def youtube_authenticate():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=creds)

# ────────────────────────────────────────────────
#  GET RANDOM MEME FROM REDDIT
# ────────────────────────────────────────────────
def get_reddit_meme():
    sub = random.choice(REDDIT_SUBS)
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
    headers = {"User-agent": "MemeBot/1.0"}
    res = requests.get(url, headers=headers)
    posts = res.json()["data"]["children"]

    valid_posts = [
        p["data"] for p in posts
        if not p["data"].get("over_18")
        and p["data"].get("url", "").endswith((".jpg", ".png", ".jpeg"))
        and len(p["data"]["title"]) > 5
    ]

    if not valid_posts:
        raise Exception("No valid meme posts found.")

    post = random.choice(valid_posts)
    return post["title"], post["url"], f"https://reddit.com{post['permalink']}"

# ────────────────────────────────────────────────
#  CREATE MEME IMAGE (SQUARE WITH BORDER)
# ────────────────────────────────────────────────
def make_meme_image(title, img_url, count):
    img_data = requests.get(img_url).content
    img = Image.open(BytesIO(img_data)).convert("RGB")

    # Resize + center crop to square
    img.thumbnail(OUTPUT_SIZE, Image.LANCZOS)
    bg = Image.new("RGB", OUTPUT_SIZE, (0, 0, 0))
    bg.paste(img, ((OUTPUT_SIZE[0] - img.width)//2, (OUTPUT_SIZE[1] - img.height)//2))
    img_path = os.path.join(OUTPUT_DIR, f"meme_{count:03}.jpg")
    bg.save(img_path)
    return img_path

# ────────────────────────────────────────────────
#  TURN IMAGE INTO SHORT VIDEO
# ────────────────────────────────────────────────
def image_to_video(img_path, duration=8):
    # main meme clip
    main_clip = ImageClip(img_path).set_duration(duration - 3)

    # create outro image with "Subscribe Please ❤️"
    outro_img = Image.new("RGB", OUTPUT_SIZE, (0, 0, 0))
    draw = ImageDraw.Draw(outro_img)

    try:
        font = ImageFont.truetype("arial.ttf", 80)
    except:
        font = ImageFont.load_default()

    text = "Subscribe Please ❤️"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((OUTPUT_SIZE[0] - text_w)//2, (OUTPUT_SIZE[1] - text_h)//2)
    draw.text(pos, text, fill=(255, 255, 255), font=font)

    outro_path = img_path.replace(".jpg", "_subscribe.jpg")
    outro_img.save(outro_path)

    outro_clip = ImageClip(outro_path).set_duration(3)
    final_clip = concatenate_videoclips([main_clip, outro_clip])

    if os.path.exists(MUSIC_FILE):
        music = AudioFileClip(MUSIC_FILE).subclip(0, final_clip.duration).volumex(0.4)
        final_clip = final_clip.set_audio(CompositeAudioClip([music]))

    out_path = img_path.replace(".jpg", ".mp4")
    final_clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    final_clip.close()
    return out_path

# ────────────────────────────────────────────────
#  UPLOAD VIDEO TO YOUTUBE
# ────────────────────────────────────────────────
def upload_to_youtube(youtube, video_file, title, description):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["memes", "funny", "reddit memes", "dankmemes"],
            "categoryId": "23",  # Comedy
        },
        "status": {"privacyStatus": "public"},
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=video_file
    )
    response = request.execute()
    print(f"✅ Uploaded: https://youtu.be/{response['id']}")

# ────────────────────────────────────────────────
#  MAIN WORKFLOW
# ────────────────────────────────────────────────
def generate_and_upload(youtube, count):
    try:
        title, img_url, post_link = get_reddit_meme()
        print(f"🤣 Meme: {title}\n📷 {img_url}")

        img_path = make_meme_image(title, img_url, count)
        video_path = image_to_video(img_path)

        upload_to_youtube(
            youtube,
            video_path,
            title=title,
            description=f"{title}\n\nFrom Reddit: {post_link}\n#memes #funny #reddit"
        )
    except Exception as e:
        print("⚠️ Error:", e)

# ────────────────────────────────────────────────
#  LOOP CONTINUOUSLY EVERY 3 HOURS
# ────────────────────────────────────────────────
def main():
    youtube = youtube_authenticate()
    count = 1
    while True:
        print("⏰ Generating and uploading a new Reddit meme video...")
        generate_and_upload(youtube, count)
        count += 1
        print(f"✅ Done! Waiting 3 hours before next upload...")
        time.sleep(POST_INTERVAL)

# ────────────────────────────────────────────────
#  START
# ────────────────────────────────────────────────
if __name__ == "__main__":
    main()
