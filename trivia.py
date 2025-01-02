import os
import random
from moviepy.editor import (TextClip, CompositeVideoClip, AudioFileClip,
                            concatenate_videoclips, ColorClip, VideoFileClip)
import requests
import unicodedata
from moviepy.audio.fx.all import volumex
from moviepy.config import change_settings
import html
from melo.api import TTS
import time

# Set up ImageMagick (if needed)
change_settings({})

# Initialize TTS
speed = 1
device = 'auto'
tts = TTS(language='EN', device=device)
speaker_ids = tts.hps.data.spk2id

# Trivia API endpoint with random category


def get_random_category_api():
    while True:
        # Randomly select a category number between 9 and 32
        category_number = random.randint(9, 32)
        trivia_api = f"https://opentdb.com/api.php?amount=5&category={category_number}&type=multiple"
        response = requests.get(trivia_api)
        if response.status_code == 200:
            data = response.json()
            if data.get("response_code") == 0 and data.get("results"):
                # Get the first word of the category
                category = data['results'][0]['category'].split()[0]
                # Keep only letters
                category = ''.join(filter(str.isalpha, category))
                return trivia_api, category


# Trivia API endpoint and category
TRIVIA_API, TRIVIA_CATEGORY = get_random_category_api()

# Create output directories if they don't exist
os.makedirs("output/audio", exist_ok=True)
os.makedirs("output/videos", exist_ok=True)


def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


def fetch_trivia():
    print(TRIVIA_API)
    max_retries = 5  # Maximum number of retries
    retry_delay = 1  # Initial delay in seconds
    for attempt in range(max_retries):
        response = requests.get(TRIVIA_API)
        if response.status_code == 200:
            data = response.json()
            trivia_list = []
            for item in data.get("results", []):
                question = html.unescape(item["question"])
                correct_answer = html.unescape(item["correct_answer"])
                incorrect_answers = [html.unescape(ans)
                                     for ans in item["incorrect_answers"]]
                # Create a list of all answers and shuffle them
                all_answers = [correct_answer] + incorrect_answers
                random.shuffle(all_answers)
                # Store the index of the correct answer
                correct_index = all_answers.index(correct_answer)
                trivia_list.append(
                    (question, correct_answer, all_answers, correct_index))
            return trivia_list
        elif response.status_code == 429:
            print(
                f"Received 429 Too Many Requests. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)  # Wait before retrying
            retry_delay *= 2  # Exponential backoff
        else:
            print(f"Error: {response.status_code}")
            break  # Exit on other errors
    return []  # Return an empty list if all retries fail


def generate_audio(trivia_list):
    audio_files = []
    for i, (question, correct_answer, all_answers, _) in enumerate(trivia_list):
        # Normalize text
        question = normalize_text(question)
        answers_text = normalize_text(
            ". ".join([f"Option {idx + 1}: {ans}" for idx, ans in enumerate(all_answers)]))
        correct_answer = normalize_text(correct_answer)

        # Generate paths
        question_output_path = f"output/audio/trivia_q_{i}.wav"
        options_output_path = f"output/audio/trivia_options_{i}.wav"
        answer_output_path = f"output/audio/trivia_a_{i}.wav"

        tts.tts_to_file(
            f"{question}",
            speaker_ids['EN-BR'],
            question_output_path,
            speed=speed
        )

        tts.tts_to_file(
            f"{answers_text}", speaker_ids['EN-BR'],
            options_output_path, speed=speed
        )

        tts.tts_to_file(
            f"The correct answer is {correct_answer}.", speaker_ids['EN-BR'],
            answer_output_path, speed=speed
        )

        audio_files.append(
            [question_output_path, options_output_path, answer_output_path])
    return audio_files


def fetch_ticking_sound():
    sound_path = "output/ticking.mp3"
    return sound_path


def create_video_clips(trivia_list, audio_files, ticking_sound):
    clips = []

    # Create a persistent category title clip with duration set dynamically
    def create_category_clip(duration):
        return TextClip(
            TRIVIA_CATEGORY,
            fontsize=80,
            color='white',
            size=(1080, 100),  # Height of the title bar
            font="Arial-Bold",
            bg_color="#003366"
        ).set_position(("center", "top")).set_duration(duration)

    for i, ((question, correct_answer, all_answers, correct_index), (q_path, opt_path, a_path)) in enumerate(zip(trivia_list, audio_files)):
        # Generate background color
        background_color = (120, 120, 255)

        # Question clip
        question_audio = AudioFileClip(q_path)
        question_duration = question_audio.duration

        # Create the category clip for the question duration
        category_clip = create_category_clip(question_duration)

        question_background = ColorClip(
            size=(1080, 1920), color=(224, 247, 250), duration=question_duration)

        question_clip = TextClip(
            question,
            fontsize=70,
            color='#003366',
            size=(1080, 1920),
            method="caption",
            align="center",
            font="Arial-Bold"
        ).set_duration(question_duration).set_position("center")

        question_clip_with_bg = CompositeVideoClip(
            [question_background, category_clip, question_clip])
        question_clip_with_bg = question_clip_with_bg.set_audio(question_audio)
        clips.append(question_clip_with_bg)

        # Options clip
        options_audio = AudioFileClip(opt_path)
        options_duration = options_audio.duration

        # Create the category clip for the options duration
        category_clip = create_category_clip(options_duration)

        # Create text for all options
        options_text = f"{question}\n\n" + "\n\n".join(
            [f"{idx + 1}) {ans}" for idx, ans in enumerate(all_answers)])
        options_clip = TextClip(
            options_text,
            fontsize=70,
            color='#003366',
            size=(1080, 1920),
            method="caption",
            align="center",
            font="Arial-Bold"
        ).set_duration(options_duration)

        options_background = ColorClip(
            size=(1080, 1920), color=(224, 247, 250), duration=options_duration)
        options_clip_with_bg = CompositeVideoClip(
            [options_background, category_clip, options_clip])
        options_clip_with_bg = options_clip_with_bg.set_audio(options_audio)
        clips.append(options_clip_with_bg)

        # Timer clip with options displayed
        ticking_audio = AudioFileClip(ticking_sound)
        ticking_audio = volumex(ticking_audio, 0.8)
        timer_clip = CompositeVideoClip(
            [options_clip_with_bg]).set_duration(
            ticking_audio.duration).set_audio(ticking_audio)
        clips.append(timer_clip)

        # Answer clip
        answer_audio = AudioFileClip(a_path)
        answer_duration = answer_audio.duration

        # Create the category clip for the answer duration
        category_clip = create_category_clip(answer_duration)

        answer_background = ColorClip(
            size=(1080, 1920), color=background_color, duration=answer_duration)
        answer_text = f"The correct answer is:\n\n{correct_answer}\n(Option {correct_index + 1})"
        answer_clip = TextClip(
            answer_text,
            fontsize=70,
            color='White',
            size=(1080, 1920),
            method="caption",
            align="center",
            font="Arial-Bold"
        ).set_duration(answer_duration)

        answer_clip_with_bg = CompositeVideoClip(
            [answer_background, category_clip, answer_clip])
        answer_clip_with_bg = answer_clip_with_bg.set_audio(answer_audio)
        clips.append(answer_clip_with_bg)

    return clips


def generate_video(clips, output_name="trivia_video.mp4"):
    end_credit_video = VideoFileClip('output/YoutubeTriviaEndCredit.mp4')
    clips.append(end_credit_video)
    final_video = concatenate_videoclips(clips, method="compose")

    timestamp = int(time.time())
    unique_output_name = f"{output_name.split('.')[0]}_{TRIVIA_CATEGORY}_{timestamp}.mp4"
    final_path = f"output/videos/{unique_output_name}"
    
    # Modified encoding parameters for Ubuntu
    final_video.write_videofile(
        final_path,
        fps=5,
        codec='libx264',  # Changed from h264_nvenc
        audio_codec="aac",
    )
    print(f"Video saved at {final_path}")


def cleanup_audio_files(audio_files):
    for audio_set in audio_files:
        for audio_file in audio_set:
            if os.path.exists(audio_file):
                os.remove(audio_file)  # Delete the audio file
                print(f"Deleted audio file: {audio_file}")


def main():
    trivia_list = fetch_trivia()
    if not trivia_list:
        print("Failed to fetch trivia. Exiting.")
        return

    audio_files = generate_audio(trivia_list)
    ticking_sound = fetch_ticking_sound()
    clips = create_video_clips(trivia_list, audio_files, ticking_sound)
    generate_video(clips)

    # Clean up audio files after video generation
    cleanup_audio_files(audio_files)


if __name__ == "__main__":
    main()
