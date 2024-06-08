import json
from openai import OpenAI
import os
from pydub import AudioSegment
import datetime
import logging

logging.basicConfig(level=logging.INFO)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), organization=os.getenv("OPENAI_ORG_ID"))


def _parse_timestamp(filename) -> float | None:
    try:
        parts = filename.split('-')
        timestamp_str = parts[-1].split('.')[0]
        timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").timestamp()
        return timestamp
    except Exception as e:
        print(f"Error parsing timestamp from {filename}: {e}")
        return None


def merge_audio_files(directory='audio_output') -> None:
    try:
        audio_files = [f for f in os.listdir(directory) if f.endswith('.mp3')]
        if not audio_files:
            print("No audio files found in the directory.")
            return

        user_audio_data = {}  # Dictionary to store audio data for each user

        for file in audio_files:
            parts = file.split('-')
            user_id = parts[1]  # Assuming the user ID is between the first and second '-'
            timestamp = _parse_timestamp(file)
            if timestamp is not None:
                if user_id not in user_audio_data:
                    user_audio_data[user_id] = []
                user_audio_data[user_id].append((file, timestamp))

        if not user_audio_data:
            print("No valid timestamps found in filenames.")
            return

        for user_id, audio_data in user_audio_data.items():
            audio_data.sort(key=lambda x: x[1])
            earliest_timestamp = audio_data[0][1]

            for i in range(len(audio_data)):
                audio_data[i] = (audio_data[i][0], audio_data[i][1] - earliest_timestamp)

            merged_audio = AudioSegment.silent(duration=0)
            last_end_time = 0

            for file, timestamp in audio_data:
                try:
                    print(f"Loading file: {file}")
                    audio = AudioSegment.from_mp3(os.path.join(directory, file))
                    print(f"Loaded file: {file}, duration: {len(audio)} ms")
                except Exception as e:
                    print(f"Error loading {file}: {e}")
                    continue

                start_time = timestamp
                if start_time > last_end_time:
                    gap_duration = start_time - last_end_time
                    print(f"Adding silence of duration: {gap_duration} seconds")
                    silence = AudioSegment.silent(duration=gap_duration * 1000)
                    merged_audio += silence

                merged_audio += audio
                last_end_time = start_time + len(audio) / 1000

                print(f"Added {file} to merged audio, new duration: {len(merged_audio)} ms")

            output_timestamp = datetime.datetime.utcfromtimestamp(earliest_timestamp).strftime('%Y%m%d%H%M%S')
            output_file = f"merged_audio_{user_id}_{output_timestamp}.mp3"
            output_path = os.path.join("merged_audios", output_file)
            merged_audio.export(output_path, format="mp3")
            print(f"Merged audio file created for user {user_id} with timestamp {output_timestamp}: {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")


def process_voice_to_text(audio_path) -> dict:
    audio_file = open("merged_audios\\" + audio_path, "rb")
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="verbose_json",
        timestamp_granularities=["segment"]
    )

    parts = audio_path.split('_')
    timestamp_str = parts[-1].split('.')[0]
    timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
    timestamped_transcription = {}
    for segment in transcription.segments:
        start_time = timestamp + datetime.timedelta(seconds=int(segment["start"]))
        output_timestamp = start_time.strftime('%Y%m%d%H%M%S')
        text = segment["text"]
        timestamped_transcription[output_timestamp] = text

    return timestamped_transcription


def transcript_conversation() -> str:
    files = [f for f in os.listdir("merged_audios") if os.path.isfile(os.path.join("merged_audios", f))]
    combined_transcription = {}
    for f in files:
        transcription = process_voice_to_text(f)
        combined_transcription.update(transcription)  # Update the main dictionary with the new transcription

    sorted_transcription = sorted(combined_transcription.items())  # Sort the dictionary by timestamp
    transcription_string = ""
    for timestamp, transcription in sorted_transcription:
        transcription_string += f"{timestamp}: {transcription}\n"

    return transcription_string


def summarize_conversation() -> str:
    pass


if __name__ == '__main__':
    print(transcript_conversation())
    # merge_audio_files()

# todo: make it so each user's audio is separated into different files, generate transcription separately,
#  use timestamps to combine, then summarize the conversation.
