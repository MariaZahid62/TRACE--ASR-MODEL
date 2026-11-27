
import re


def clean_text(text):
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", str(text).lower())
    return [word for word in words if word not in STOP_WORDS]


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "after", "before", "be", "been", "being", "but",
    "by", "can", "could", "did", "do", "does", "for", "from", "had",
    "has", "have", "he", "her", "here", "hers", "him", "his", "how", "i",
    "if", "in", "into", "is", "it", "its",     "me", "meeting", "more", "most", "my",
    "no", "not", "of", "on", "or", "our", "ours", "she", "so", "than",
    "that", "the", "their", "theirs", "them", "then", "there", "these",
    "they", "this", "those", "to", "too", "us", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with",
    "would", "you", "your", "yours",
}
