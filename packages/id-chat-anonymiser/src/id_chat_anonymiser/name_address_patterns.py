"""Patterns for names and street addresses: the backstop under the NER model.

NusaBert (R1) finds most names and addresses, but the dev run showed where
it slips (docs/results-anonymiser.md):
- every address it missed was an alley ("Gg. Laswi No. 3");
- many missed names were a single word, often lower case, right after a
  word that announces a name: "a.n budi", "saya rahmi", "nama: citra", or
  in brackets after a NIK.

These patterns catch those shapes whatever the model does, and they run in
R0 too. They are deliberately narrow: a name is only taken after a cue
word, and a street only when a house number follows.

Built from general Indonesian chat usage and the dev templates, never from
held-out output. With only 17 name slots in the dev templates, dev numbers
flatter these rules; held-out is the real test.
"""

from presidio_analyzer import Pattern

from id_chat_anonymiser.reference import BANKS

# Whose name is asked for: "nama anak dan NIK nya?" names no one.
RELATIONS = "anak istri suami ayah adik orang tua".split()
# Words that follow a cue word but are not names: pronouns, particles,
# greetings, common chat verbs and the words for the data asked next.
# Without them "saya mau booking" or "nama dan nomor hp" would be redacted.
_CHAT_WORDS = (
    "saya aku kami kita dia ya yaa iya kak ka kakak gan sis bro mas mbak pak bu bapak ibu "
    "dan atau yang dengan di ke dari untuk buat sudah udah belum mau ingin pengen bisa "
    "boleh akan lagi juga saja aja sih dong deh nih kok tuh ok oke nanti tadi sekarang "
    "besok sendiri berdua siapa apa tidak nggak gak ga enggak tanya cek kirim transfer "
    "bayar kabari tunggu ambil setuju minat tertarik punya ada perlu butuh nik ktp hp wa "
    "no nomor email alamat rekening rek terima kasih makasih mohon tolong pesan booking "
    "order beli sesuai pemilik lengkap penerima selamat halo hai rp idr"
).split()
NOT_NAMES = [*_CHAT_WORDS, *RELATIONS]
MAX_NAME_WORDS = 3
# A house number must follow the street name within this many words, so
# "lagi di jalan ke kantor" is never taken for an address.
MAX_STREET_NAME_WORDS = 5
STREET_WORDS = "gang|gg|jalan|jln|jl"

# Letters, accents, apostrophes (straight or curly) and hyphens: "Ma'ruf".
_IN_A_NAME = r"\p{L}\p{M}'\u2019\-"
_NOT_A_NAME = rf"(?!(?:{'|'.join(NOT_NAMES)})(?![{_IN_A_NAME}]))"
_NAME_WORD = rf"{_NOT_A_NAME}\p{{L}}[{_IN_A_NAME}]*"
NAME = (
    rf"(?<![{_IN_A_NAME}]){_NAME_WORD}"
    rf"(?:[ ]+{_NAME_WORD}){{0,{MAX_NAME_WORDS - 1}}}(?![{_IN_A_NAME}])"
)

# "a.n Budi", "atas nama Budi", "nama saya Budi", "namanya: Budi".
_AFTER_NAME_WORD = (
    r"(?<=\b(?:a\.n\.?|a/n|atas[ ]+nama|nama(?:nya)?"
    rf"(?:[ ]+(?:saya|lengkap|pemilik|penerima|{'|'.join(RELATIONS)}))?)[ ]*:?[ ]*)"
)
# "saya Budi" or "ok saya budi, ..." opening a message, ending at a comma,
# full stop or the end of the line: an introduction, not "saya mau ...".
_INTRODUCTION = (
    r"(?<=^[ ]*(?:(?:ok|oke|iya|ya|halo|hai|permisi|pagi|siang|sore|malam)[ ,.!]+)?"
    r"saya(?:[ ]+sendiri)?[ ]+)"
)
# Capitalised, up to three words ("Irma Hassanah"); lower case, one word
# ("rahmi"), so "saya rasa cocok" isn't read as a two-word name.
_INTRODUCED_NAME = rf"(?:(?-i:(?=\p{{Lu}})){NAME}|(?<![{_IN_A_NAME}]){_NAME_WORD})"
_INTRODUCTION_END = r"(?=[ ]*(?:[,.!]|$))"
# "3201010101010001 (Budi Santoso)": brackets right after a 10-16 digit number.
_IN_BRACKETS_AFTER_NUMBER = r"(?<=(?:\d[ .\-]?){9}\d[ ]*\([ ]*)"
# "budi 081234567890" or "Budi Santoso, 3201...": a name opening a message
# or line, right before a phone, NIK or account number of 10 or more digits
# (on the same line or the next). A bank name opens "Mandiri 5118..." the
# same way, so it can't be the first word here; it can be a surname.
_OPENING_A_LINE = rf"(?<=^[ ]*)(?!(?:{'|'.join(BANKS)})\b)"
_BEFORE_A_LONG_NUMBER = r"(?=[ ]*[,/]?\s*\+?\(?\d(?:[ .\-()]*\d){9})"
# "kak Ulva", "Pak Budi Santoso": a capitalised word after an honorific.
# Lower case is left out: "kak barang yg datang salah" names no one.
_AFTER_HONORIFIC = r"(?<=\b(?:kak|ka|pak|bu|bapak|ibu|mas|mbak|mba|bang)[ ]+)(?-i:(?=\p{Lu}))"


def name_patterns() -> list[Pattern]:
    return [
        Pattern("after a name word", _AFTER_NAME_WORD + NAME, 0.6),
        Pattern("introduction", _INTRODUCTION + _INTRODUCED_NAME + _INTRODUCTION_END, 0.5),
        Pattern("in brackets", _IN_BRACKETS_AFTER_NUMBER + NAME + r"(?=[ ]*\))", 0.6),
        Pattern("before a number", _OPENING_A_LINE + NAME + _BEFORE_A_LONG_NUMBER, 0.5),
        Pattern("after an honorific", _AFTER_HONORIFIC + NAME, 0.5),
    ]


def street_patterns() -> list[Pattern]:
    # "Gg. Laswi No. 3", "Jl. Merdeka no 5 RT 01/RW 02". The street name may
    # hold abbreviations with dots ("Gang HOS. Cokroaminoto No. 1").
    street = Pattern(
        "street with a house number",
        rf"\b(?:{STREET_WORDS})\.?[ ]+(?:\w[\w.'/\-]*[ ]+){{1,{MAX_STREET_NAME_WORDS}}}?"
        r"no\.?[ ]*\d+[a-z]?\b"
        r"(?:[ ,]+rt\.?[ ]*\d{1,3}[ ]*/[ ]*rw\.?[ ]*\d{1,3}\b)?",
        0.6,
    )
    return [street]
