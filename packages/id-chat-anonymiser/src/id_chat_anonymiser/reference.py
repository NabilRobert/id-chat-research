"""Indonesian reference lists shared by the recognisers and the generator.

Public facts about how Indonesian identifiers are built, not data about
anyone: operator prefixes, region codes, bank names.
"""

# Mobile prefixes in use by Indonesian operators (without the leading 0).
MOBILE_PREFIXES = (
    "811 812 813 814 815 816 817 818 819 821 822 823 831 832 833 838 851 852 853 "
    "855 856 857 858 859 877 878 881 882 883 885 887 888 889 895 896 897 898 899"
).split()
# Landline area codes of large cities (without the leading 0).
AREA_CODES = ("21", "22", "24", "31", "61", "274", "341", "361", "411")
# NIK province codes (the first two digits), from the Kemendagri region codes.
NIK_PROVINCE_CODES = (
    "11 12 13 14 15 16 17 18 19 21 31 32 33 34 35 36 51 52 53 61 62 63 64 65 "
    "71 72 73 74 75 76 81 82 91 92 94"
).split()
# Women's NIKs add 40 to the birth day.
NIK_WOMAN_DAY_OFFSET = 40
# Region letters on Indonesian number plates.
PLATE_REGIONS = (
    "A B D E F G H K L M N P R S T W Z AA AB AD AE AG BA BB BD BE BG BH BK BL BM BN BP "
    "DA DB DD DE DG DH DK DL DM DN DR DT EA EB ED KB KH KT KU PA PB"
).split()
BANKS = ("BCA", "BRI", "BNI", "Mandiri", "BSI", "CIMB", "Permata")
