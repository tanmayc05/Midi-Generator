import json
import numpy as np
# from tensorflow import keras
import keras
import music21 as m21
from preprocess import SEQUENCE_LENGTH, MAPPINGS_PATH
import random

class MelodyGenerator:
    """A class that wraps the LSTM model and offers utilities to generate melodies."""

    def __init__(self, model_path="models/chord_prog3.h5"):
        """Constructor that initialises TensorFlow model"""

        self.model_path = model_path
        self.model = keras.models.load_model(model_path)

        with open(MAPPINGS_PATH, "r") as fp:
            self._mappings = json.load(fp)

        self._start_symbols = ["/"] * SEQUENCE_LENGTH


    def generate_melody(self, seed, num_steps, max_sequence_length, temperature):
        """Generates a melody using the DL model and returns a midi file.

        :param seed (str): Melody seed with the notation used to encode the dataset
        :param num_steps (int): Number of steps to be generated
        :param max_sequence_len (int): Max number of steps in seed to be considered for generation
        :param temperature (float): Float in interval [0, 1]. Numbers closer to 0 make the model more deterministic.
            A number closer to 1 makes the generation more unpredictable.

        :return melody (list of str): List with symbols representing a melody
        """

        # create seed with start symbols
        seed = seed.split()
        melody = seed
        seed = self._start_symbols + seed

        # map seed to int
        seed = [self._mappings[symbol] for symbol in seed]

        for _ in range(num_steps):

            # limit the seed to max_sequence_length
            seed = seed[-max_sequence_length:]

            # one-hot encode the seed
            onehot_seed = keras.utils.to_categorical(seed, num_classes=len(self._mappings))
            # (1, max_sequence_length, num of symbols in the vocabulary)
            onehot_seed = onehot_seed[np.newaxis, ...]

            # make a prediction
            probabilities = self.model.predict(onehot_seed)[0]
            # [0.1, 0.2, 0.1, 0.6] -> 1
            output_int = self._sample_with_temperature(probabilities, temperature)

            # update seed
            seed.append(output_int)

            # map int to our encoding
            output_symbol = [k for k, v in self._mappings.items() if v == output_int][0]

            # check whether we're at the end of a melody
            if output_symbol == "/":
                break

            # update melody
            melody.append(output_symbol)

        return melody


    def _sample_with_temperature(self, probabilites, temperature):
        """Samples an index from a probability array reapplying softmax using temperature

        :param predictions (nd.array): Array containing probabilities for each of the possible outputs.
        :param temperature (float): Float in interval [0, 1]. Numbers closer to 0 make the model more deterministic.
            A number closer to 1 makes the generation more unpredictable.

        :return index (int): Selected output symbol
        """
        predictions = np.log(probabilites) / temperature
        probabilites = np.exp(predictions) / np.sum(np.exp(predictions))

        choices = range(len(probabilites)) # [0, 1, 2, 3]
        index = np.random.choice(choices, p=probabilites)

        return index


    def save_melody(self, melody, step_duration=0.25, format="midi", file_name="mel.mid"):
        """Converts a melody into a MIDI file

        :param melody (list of str):
        :param min_duration (float): Duration of each time step in quarter length
        :param file_name (str): Name of midi file
        :return:
        """

        # create a music21 stream
        stream = m21.stream.Stream()

        start_symbol = None
        step_counter = 1

        # parse all the symbols in the melody and create note/rest objects
        for i, symbol in enumerate(melody):

            # handle case in which we have a note/rest
            if symbol != "_" or i + 1 == len(melody):

                # ensure we're dealing with note/rest beyond the first one
                if start_symbol is not None:

                    quarter_length_duration = step_duration * step_counter # 0.25 * 4 = 1

                    # handle chord with rest
                    if start_symbol == "R":
                        m21_event = m21.note.Rest(quarterLength=quarter_length_duration)

                    # handle chord
                    elif "." in start_symbol:
                        notes_in_chord = start_symbol.split(".")
                        notes = []
                        for current_note in notes_in_chord:
                            # handle rest within chord
                            if current_note == "R":
                                new_note = m21.note.Rest()
                            else:
                                new_note = m21.note.Note(int(current_note))
                            new_note.quarterLength = quarter_length_duration
                            notes.append(new_note)

                        m21_event = m21.chord.Chord(notes)

                    # handle note
                    else:
                        m21_event = m21.note.Note(int(start_symbol), quarterLength=quarter_length_duration)

                    stream.append(m21_event)

                    # reset the step counter
                    step_counter = 1

                start_symbol = symbol

            # handle case in which we have a prolongation sign "_"
            else:
                step_counter += 1

        # write the m21 stream to a midi file
        stream.write(format, file_name)
        
    def create_random_seed(self):
        chord_keys = [key for key in self._mappings.keys() if key != "/"]
    
        # Choose a random chord key
        seed = random.choice(chord_keys)
         
        return seed


if __name__ == "__main__":
    mg = MelodyGenerator()
    # choose random seed from mappings.json
    seed = mg.create_random_seed()
    melody = mg.generate_melody(seed, 500, SEQUENCE_LENGTH, 0.8)
    melody.append("_")
    print(melody)
    mg.save_melody(melody)