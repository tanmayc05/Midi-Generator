import os
import music21 as m21
import json
import keras as keras
import numpy as np

TRAINING_SET_PATH = "training_set_3" # path to the dataset
ALL_SONGS_DATASET = "encoded_songs_dataset" # text files of encoded songs
MAPPINGS_PATH = "mappings.json" # mappings file
RATINGS_PATH = "ratings.json" # ratings file
ACCEPTABLE_DURATIONS = [0.25, 0.5, 0.75, 1.0, 1.5, 2, 3, 4] # in quarter length
SEQUENCE_LENGTH = 64
 
RATINGS = [] # ratings for each song
 
def load_songs(data_path):
    songs = []
    global RATINGS
    RATINGS = []  # Initialize to empty

    for path, subdirs, files in os.walk(data_path):
        for file in files:
            if file.endswith(".mid"):
                # Check if in Rated_Generations directory
                if os.path.basename(path) == 'Rated_Generations':
                    with open(RATINGS_PATH, "r") as ratings_file:
                        ratings = json.load(ratings_file)
                        RATINGS.append(ratings[file])
                else:
                    # Assign default rating
                    RATINGS.append(4)

                song = m21.converter.parse(os.path.join(path, file))
                songs.append(song)
                
    return songs

def has_acceptable_durations(song, acceptable_durations):
    # account for chords and notes
    for note in song.flat.notesAndRests:
        if note.duration.quarterLength not in acceptable_durations:
            return False
    return True

def transpose(song):
    # Get key from the song
    parts = song.getElementsByClass(m21.stream.Part)
    measures_part0 = parts[0].getElementsByClass(m21.stream.Measure)
    key = measures_part0[0][3]  # assuming the key signature is the 5th element of the first measure
    # Estimate key using music21
    key = song.analyze("key")
    # Get interval for transposition. E.g., Bmaj -> Cmaj
    if key.mode == "major":
        interval = m21.interval.Interval(key.tonic, m21.pitch.Pitch("C"))
    elif key.mode == "minor":
        interval = m21.interval.Interval(key.tonic, m21.pitch.Pitch("A"))
    # Transpose song by calculated interval
    transposed_song = song.transpose(interval)
    return transposed_song

def extract_melody_and_chords(song):
    # Extract melody and chords from the song
    # Initialize melody and chords
    melody = m21.stream.Part()
    chords = m21.stream.Part()
    
    # Get melody and chords notes from the song
    for element in song.flat:
        # If the element is a Note
        if isinstance(element, m21.note.Note):
            melody.append(element)
        # If the element is a Chord
        elif isinstance(element, m21.chord.Chord):
            chords.append(element)
    return melody, chords

def encode_song(song, time_step=0.25):
    # Convert song into string of characters
    encoded_song = []
    for event in song.flat.notesAndRests:
        # If it's a note
        if isinstance(event, m21.note.Note):
            symbol = event.pitch.midi
        # If it's a rest
        elif isinstance(event, m21.note.Rest):
            symbol = "R"
        # If it's a chord
        else:
            symbol = ".".join(str(n) for n in event.normalOrder)
        # Append the encoded symbol
        steps = int(event.duration.quarterLength / time_step)
        for step in range(steps):
            if step == 0:
                encoded_song.append(symbol)
            else:
                encoded_song.append("_")
    encoded_song = " ".join(map(str, encoded_song))
    return encoded_song


def preprocess(data_path):
    # Load songs
    print("Loading songs...")
    songs = load_songs(data_path)
    print(f"Loaded {len(songs)} songs.")
    
    for i, song in enumerate(songs):
        # Filter out songs that have non-acceptable durations
        if not has_acceptable_durations(song, ACCEPTABLE_DURATIONS):
            continue
        
        # Transpose songs to Cmaj/Amin
        song = transpose(song)
        
        encoded_song = encode_song(song)
                
        # Save songs to text file
        save_path = os.path.join(ALL_SONGS_DATASET, f"song_{i}.txt")
        with open(save_path, "w", encoding="utf-8") as file:
            file.write(encoded_song)
            
def merge_dataset_to_file(dataset_path, file_path):
    # Merge all songs into a single file
    new_song_delimiter = "/ " * SEQUENCE_LENGTH
    songs = ""
    for path, subdirs, files in os.walk(dataset_path):
        for file in files:
            with open(os.path.join(path, file), "r") as f:
                song = f.read()
                songs += song + " " + new_song_delimiter
    songs = songs[:-1]
    
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(songs)
    return songs

def create_mapping(songs, mappings_file):
    mappings = {}
    
    # Identify the vocabulary
    songs = songs.split()
    vocabulary = list(set(songs))
    
    # Create mappings
    for i, symbol in enumerate(vocabulary):
        mappings[symbol] = i
    
    # Save the mappings to a JSON file
    with open(mappings_file, "w", encoding="utf-8") as file:
        json.dump(mappings, file, indent=4)

def convert_songs_to_int(songs):
    # Load mappings
    with open(MAPPINGS_PATH, "r") as file:
        mappings = json.load(file)
    
    # Convert songs to int
    int_songs = []
    
    songs = songs.split()
    for symbol in songs:
        int_songs.append(mappings[symbol])
        
    return int_songs

def generate_training_sequences(sequence_length):
    # Load songs and map them to int
    songs = open("dataset.txt", "r").read()
    int_songs = convert_songs_to_int(songs)
    inputs = []
    targets = []
    weights = []

    num_songs = len(RATINGS)
    song_start_idx = 0

    for song_idx in range(num_songs):
        int_song = int_songs[song_start_idx:song_start_idx + len(int_songs)]
        rating = RATINGS[song_idx]
        
        num_sequences = len(int_song) - sequence_length
        for i in range(num_sequences):
            inputs.append(int_song[i:i + sequence_length])
            targets.append(int_song[i + sequence_length])
            weights.append(rating)
        
        song_start_idx += len(int_song)
    print('One-hot encoding time!')
    # One-hot encode the sequences
    vocabulary_size = len(set(int_songs))
    inputs = keras.utils.to_categorical(inputs, num_classes=vocabulary_size)
    targets = np.array(targets)
    weights = np.array(weights)
    
    print('One-hot encoding done!')
    print('Inputs shape:', inputs.shape)
    print('Targets shape:', targets.shape)
    print('Weights shape:', weights.shape)    
    return inputs, targets, weights



if __name__ == "__main__":
    preprocess(TRAINING_SET_PATH) 
    
    # songs = merge_dataset_to_file(ALL_SONGS_DATASET, "dataset.txt")
    
    # create_mapping(songs, MAPPINGS_PATH)
    
    inputs, outputs, weights = generate_training_sequences(SEQUENCE_LENGTH)
