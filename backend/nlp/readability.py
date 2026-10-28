import re
import math


def count_syllables(word: str) -> int:
    word = word.lower()
    if len(word) <= 3:
        return 1
    vowels = "aeiouáéíóúü"
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
        count += 1
    return max(1, count)


def analyze_readability(text: str) -> dict:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()
    total_words = len(words)
    total_sentences = len(sentences)
    total_chars = len(text.replace(" ", ""))

    if total_sentences == 0 or total_words == 0:
        return {
            "word_count": 0,
            "sentence_count": 0,
            "avg_words_per_sentence": 0,
            "avg_chars_per_word": 0,
            "flesch_reading_ease": 0,
            "flesch_kincaid_grade": 0,
            "coleman_liau_index": 0,
            "readability_level": "N/A"
        }

    avg_words_per_sentence = total_words / total_sentences
    avg_chars_per_word = total_chars / total_words if total_words > 0 else 0

    total_syllables = sum(count_syllables(w) for w in words)

    flesch = 206.835 - 1.015 * avg_words_per_sentence - 84.6 * (total_syllables / total_words)
    flesch = max(0, min(100, flesch))

    fk_grade = 0.39 * avg_words_per_sentence + 11.8 * (total_syllables / total_words) - 15.59
    fk_grade = max(0, fk_grade)

    L = (total_chars / total_words) * 100
    S = (total_sentences / total_words) * 100
    cl_index = 0.0588 * L - 0.296 * S - 15.8
    cl_index = max(0, cl_index)

    if flesch >= 90:
        level = "Muy fácil"
    elif flesch >= 80:
        level = "Fácil"
    elif flesch >= 70:
        level = "Bastante fácil"
    elif flesch >= 60:
        level = "Estándar"
    elif flesch >= 50:
        level = "Bastante difícil"
    elif flesch >= 30:
        level = "Difícil"
    else:
        level = "Muy difícil"

    return {
        "word_count": total_words,
        "sentence_count": total_sentences,
        "avg_words_per_sentence": round(avg_words_per_sentence, 2),
        "avg_chars_per_word": round(avg_chars_per_word, 2),
        "total_syllables": total_syllables,
        "flesch_reading_ease": round(flesch, 2),
        "flesch_kincaid_grade": round(fk_grade, 2),
        "coleman_liau_index": round(cl_index, 2),
        "readability_level": level
    }
