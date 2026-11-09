"""Random values for the synthetic sets: personal data and look-alikes.

Names, streets and emails come from Faker's Indonesian locale. Phones, NIKs
and plates are built here, because Faker's `id_ID` versions don't look
Indonesian (phones like "(008) 377-8353", plates with region letters that
don't exist). Every value is a random draw, so none is taken from a real
person (threat model, P8). Each personal value can come out in several
written forms, the way people type them in chats.
"""

import random
from collections.abc import Callable

from faker import Faker

from id_chat_anonymiser.labels import NegativeKind, PiiType
from id_chat_anonymiser.reference import (
    AREA_CODES,
    BANKS,
    MOBILE_PREFIXES,
    NIK_PROVINCE_CODES,
    NIK_WOMAN_DAY_OFFSET,
    PLATE_REGIONS,
)

PLATE_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"


class ValueMaker:
    """Draws values for template slots from one seeded random source."""

    def __init__(self, seed: int) -> None:
        self.random = random.Random(seed)
        self.faker = Faker("id_ID")
        self.faker.seed_instance(seed)
        self._pii_makers: dict[PiiType, Callable[[], str]] = {
            PiiType.NAMA: self.name,
            PiiType.TELEPON: self.phone,
            PiiType.NIK: self.nik,
            PiiType.ALAMAT: self.address,
            PiiType.PLAT: self.plate,
            PiiType.EMAIL: self.email,
            PiiType.ID_PESANAN: self.order_id,
            PiiType.REKENING: self.account,
        }
        self._negative_makers: dict[NegativeKind, Callable[[str], str]] = {
            NegativeKind.HARGA: self.price,
            NegativeKind.PRODUK: self.product,
            NegativeKind.TANGGAL: lambda _domain: self.date(),
            NegativeKind.KM: lambda _domain: self.kilometres(),
            NegativeKind.TAHUN: lambda _domain: str(self.random.randint(2015, 2026)),
            NegativeKind.PROMO: lambda _domain: self.promo_code(),
        }

    def pii(self, pii_type: PiiType) -> str:
        return self._pii_makers[pii_type]()

    def negative(self, kind: NegativeKind, domain: str) -> str:
        return self._negative_makers[kind](domain)

    def _digits(self, count: int) -> str:
        return "".join(str(self.random.randint(0, 9)) for _ in range(count))

    def name(self) -> str:
        if self.random.random() < 0.5:
            first_name = self.faker.first_name()
            return first_name.lower() if self.random.random() < 0.3 else first_name
        # Faker adds degrees after a comma ("Juli Mardhiyah, S.Farm"); chats rarely do.
        return self.faker.name().split(",")[0]

    def address(self) -> str:
        street = self.faker.street_address()
        if self.random.random() < 0.5:
            neighbourhood = self.random.randint(1, 15)
            hamlet = self.random.randint(1, 12)
            street += f" RT {neighbourhood:02d}/RW {hamlet:02d}"
        return street

    def email(self) -> str:
        return self.faker.free_email()

    def phone(self) -> str:
        if self.random.random() < 0.15:
            return self._landline()
        prefix = self.random.choice(MOBILE_PREFIXES)
        subscriber = self._digits(self.random.randint(7, 9))
        return self._write_mobile(prefix, subscriber)

    def _write_mobile(self, prefix: str, subscriber: str) -> str:
        head, tail = subscriber[:4], subscriber[4:]
        forms = (
            f"0{prefix}{subscriber}",
            f"0{prefix}-{head}-{tail}",
            f"0{prefix} {head} {tail}",
            f"0{prefix}.{head}.{tail}",
            f"+62{prefix}{subscriber}",
            f"+62 {prefix}-{head}-{tail}",
            f"+62 {prefix} {head} {tail}",
            f"62{prefix}{subscriber}",
        )
        return self.random.choice(forms)

    def _landline(self) -> str:
        area = self.random.choice(AREA_CODES)
        number = self._digits(7)
        forms = (f"(0{area}) {number}", f"0{area}-{number}", f"(0{area}) {number[:3]}-{number[3:]}")
        return self.random.choice(forms)

    def nik(self) -> str:
        province = self.random.choice(NIK_PROVINCE_CODES)
        regency = f"{self.random.randint(1, 79):02d}"
        district = f"{self.random.randint(1, 40):02d}"
        day = self.random.randint(1, 28)
        if self.random.random() < 0.5:
            day += NIK_WOMAN_DAY_OFFSET
        birth = f"{day:02d}{self.random.randint(1, 12):02d}{self.random.randint(0, 99):02d}"
        serial = f"{self.random.randint(1, 9999):04d}"
        digits = province + regency + district + birth + serial
        if self.random.random() < 0.2:
            return " ".join(digits[start : start + 4] for start in range(0, 16, 4))
        return digits

    def plate(self) -> str:
        region = self.random.choice(PLATE_REGIONS)
        number = str(self.random.randint(1, 9999))
        letters = "".join(self.random.choices(PLATE_LETTERS, k=self.random.randint(1, 3)))
        forms = (
            f"{region} {number} {letters}",
            f"{region}{number}{letters}",
            f"{region}-{number}-{letters}",
        )
        plate = self.random.choice(forms)
        return plate.lower() if self.random.random() < 0.15 else plate

    def order_id(self) -> str:
        date = f"2026{self.random.randint(1, 12):02d}{self.random.randint(1, 28):02d}"
        forms = (
            f"INV/{date}/MPL/{self._digits(9)}",
            f"ORD-{self._digits(self.random.randint(5, 6))}",
            f"TRX{date}{self._digits(4)}",
            f"SO-{self._digits(6)}",
        )
        return self.random.choice(forms)

    def account(self) -> str:
        digits = self._digits(self.random.randint(10, 16))
        if self.random.random() < 0.25:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return digits

    def bank(self) -> str:
        return self.random.choice(BANKS)

    def price(self, _domain: str) -> str:
        millions = self.random.randint(1, 450)
        thousands = self.random.choice((0, 250, 500, 750))
        forms = (
            f"Rp {millions}.{thousands:03d}.000",
            f"Rp{millions}.{thousands:03d}.000",
            f"{millions}.{thousands:03d}.000",
            f"{millions}jt",
            f"{millions},5 jt",
            f"{self.random.randint(100, 900)}rb",
        )
        return self.random.choice(forms)

    def product(self, domain: str) -> str:
        return self.random.choice(PRODUCTS[domain])

    def date(self) -> str:
        day = self.random.randint(1, 28)
        month = self.random.randint(1, 12)
        forms = (f"{day:02d}/{month:02d}/2026", f"{day} {MONTHS[month - 1]}", f"tgl {day}")
        return self.random.choice(forms)

    def kilometres(self) -> str:
        return f"{self.random.randint(1, 120)}.{self.random.randint(0, 999):03d} km"

    def promo_code(self) -> str:
        return self.random.choice(("HEMAT50", "NOV11", "DPMURAH", "GAJIAN25", "CASHBACK10"))


MONTHS = (
    "Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember".split()
)

# Product names that look like plates, codes or names (hard negatives).
PRODUCTS: dict[str, tuple[str, ...]] = {
    "vehicles": (
        "Vario 160",
        "NMAX 155",
        "CBR 250 RR",
        "PCX 160",
        "Brio RS",
        "Xpander Ultimate",
        "Avanza 1.5 G",
        "Fortuner VRZ",
        "Ertiga GX",
        "Scoopy",
    ),
    "electronics": (
        "iPhone 15 Pro",
        "Galaxy A55",
        "Redmi Note 13",
        "TV LED 43 inch",
        "AC 1 PK",
        "kulkas 2 pintu",
        "laptop Vivobook 14",
        "Sharp Aquos",
        "mesin cuci 8 kg",
    ),
    "property": (
        "tipe 36/72",
        "tipe 45/90",
        "ruko 2 lantai",
        "apartemen studio 24 m2",
        "cluster Anggrek",
        "rumah subsidi tipe 30",
    ),
    "insurance": (
        "all risk",
        "TLO",
        "paket Gold 500",
        "plan Premier 2",
        "rawat inap kelas 1",
        "proteksi jiwa 100jt",
    ),
}
