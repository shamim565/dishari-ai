from django.core.management.base import BaseCommand
from django.db import transaction

from apps.navigation.models import Location, RouteSegment

LOCATIONS = [
    ("ENTRY", "Terminal 2 entrance", "টার্মিনাল ২ প্রবেশপথ", "Entry", Location.KIND_ENTRANCE, "", 56, 300, "A01"),
    ("BLK_A", "Check-in Block A", "চেক-ইন ব্লক A", "Block A", Location.KIND_CHECKIN, "A", 270, 126, "A10"),
    ("BLK_B", "Check-in Block B", "চেক-ইন ব্লক B", "Block B", Location.KIND_CHECKIN, "B", 270, 300, "B12"),
    ("BLK_C", "Check-in Block C", "চেক-ইন ব্লক C", "Block C", Location.KIND_CHECKIN, "C", 270, 474, "C08"),
    ("IMM", "Departure immigration", "ডিপারচার ইমিগ্রেশন", "Immigration", Location.KIND_IMMIGRATION, "", 640, 220, "I01"),
    ("SEC", "Security screening", "সিকিউরিটি স্ক্রিনিং", "Security", Location.KIND_SECURITY, "", 640, 380, "S01"),
    ("AIR", "Airside corridor", "এয়ারসাইড করিডোর", "Airside", Location.KIND_AIRSIDE, "", 840, 280, "D01"),
    ("GATE3", "Gate 3", "গেট ৩", "G3", Location.KIND_GATE, "", 930, 90, None),
    ("GATE4", "Gate 4", "গেট ৪", "G4", Location.KIND_GATE, "", 930, 180, None),
    ("GATE6", "Gate 6", "গেট ৬", "G6", Location.KIND_GATE, "", 930, 270, None),
    ("GATE8", "Gate 8", "গেট ৮", "G8", Location.KIND_GATE, "", 930, 370, "G08"),
    ("GATE12", "Gate 12", "গেট ১২", "G12", Location.KIND_GATE, "", 930, 460, None),
    ("INFO", "Information desk", "ইনফরমেশন ডেস্ক", "Info", Location.KIND_INFO, "", 500, 300, None),
    ("POLICE", "Airport police help desk", "বিমানবন্দর পুলিশ সহায়তা ডেস্ক", "Police", Location.KIND_INFO, "", 500, 370, None),
    ("WC_L", "Toilets (landside)", "টয়লেট (ল্যান্ডসাইড)", "WC", Location.KIND_TOILET, "", 500, 140, None),
    ("WC_A", "Toilets (airside)", "টয়লেট (এয়ারসাইড)", "WC", Location.KIND_TOILET, "", 790, 180, None),
    ("PRAY", "Prayer room", "নামাজের ঘর", "Prayer", Location.KIND_PRAYER, "", 500, 460, None),
    ("FOOD", "Food court", "ফুড কোর্ট", "Food", Location.KIND_FOOD, "", 790, 450, None),
    ("MED", "Medical centre", "মেডিকেল সেন্টার", "Medical", Location.KIND_MEDICAL, "", 60, 480, None),
]

SEGMENTS = [
    ("ENTRY", "BLK_B", "Walk straight through the entrance into the centre of the check-in hall.", "প্রবেশপথ থেকে সোজা এগিয়ে চেক-ইন হলের মাঝখানে আসুন।", 70),
    ("BLK_B", "BLK_A", "Take the left side of the hall towards the Biman sign - Block A is on the north side.", "হলের বাম দিক দিয়ে 'Biman Bangladesh' সাইনের দিকে যান — ব্লক A উত্তর দিকে।", 55),
    ("BLK_B", "BLK_C", "Walk to the south end of the hall - Block C is next to the prayer room signs.", "হলের দক্ষিণ দিকে যান — ব্লক C নামাজের ঘরের সাইনের পাশে।", 55),
    ("BLK_B", "INFO", "The information desk is on the right edge of the check-in hall.", "ইনফরমেশন ডেস্ক চেক-ইন হলের ডান পাশে।", 40),
    ("BLK_B", "WC_L", "Toilets are on the north-east side of the hall, near the stairs.", "টয়লেট হলের উত্তর-পূর্ব দিকে, সিঁড়ির কাছে।", 45),
    ("BLK_B", "PRAY", "The prayer room is at the south-east corner of the check-in hall.", "নামাজের ঘর চেক-ইন হলের দক্ষিণ-পূর্ব কোণে।", 50),
    ("BLK_A", "IMM", "Follow the big blue 'International Departure' sign and turn right for immigration.", "বড় নীল 'International Departure' সাইন অনুসরণ করুন — ডান দিকে ইমিগ্রেশন।", 150),
    ("BLK_B", "IMM", "Follow the big blue 'International Departure' sign straight ahead for immigration.", "বড় নীল 'International Departure' সাইন অনুসরণ করে সোজা ইমিগ্রেশনের দিকে যান।", 140),
    ("IMM", "SEC", "After the passport counter, walk ahead to security screening and join the lane.", "পাসপোর্ট কাউন্টার শেষ করে সোজা এগিয়ে সিকিউরিটি স্ক্রিনিংয়ের লাইনে দাঁড়ান।", 90),
    ("SEC", "AIR", "Pass through security and follow the corridor into the airside concourse.", "সিকিউরিটি পার হয়ে করিডোর ধরে এয়ারসাইড কনকোর্সে প্রবেশ করুন।", 75),
    ("AIR", "GATE3", "Follow the corridor north; Gate 3 is at the far end.", "করিডোর ধরে উত্তরে যান — গেট ৩ একেবারে শেষ প্রান্তে।", 170),
    ("AIR", "GATE4", "Follow the corridor north; Gate 4 is on your right.", "করিডোর ধরে উত্তরে যান — গেট ৪ ডান দিকে।", 130),
    ("AIR", "GATE6", "Gate 6 is directly ahead off the main corridor.", "গেট ৬ মূল করিডোর থেকে একটু সামনেই।", 90),
    ("AIR", "GATE8", "Follow the gate signs; Gate 8 is on the right side of the corridor.", "গেটের সাইন অনুসরণ করুন — গেট ৮ করিডোরের ডান দিকে।", 60),
    ("AIR", "GATE12", "Follow the corridor south; Gate 12 is at the far end.", "করিডোর ধরে দক্ষিণে যান — গেট ১২ শেষ প্রান্তে।", 150),
    ("AIR", "WC_A", "Toilets are beside Gate 4 on the corridor.", "টয়লেট গেট ৪-এর পাশে করিডোরের ধারে।", 55),
    ("AIR", "FOOD", "The food court is on the south side of the airside concourse.", "ফুড কোর্ট এয়ারসাইড কনকোর্সের দক্ষিণ দিকে।", 80),
    ("ENTRY", "MED", "The medical centre is just left of the entrance doors.", "মেডিকেল সেন্টার প্রবেশপথের বাঁ দিকেই।", 45),
    ("INFO", "POLICE", "The police help desk is right beside the information desk.", "পুলিশ সহায়তা ডেস্ক ইনফরমেশন ডেস্কের ঠিক পাশেই।", 20),
]


class Command(BaseCommand):
    help = "Seed the HSIA terminal layout: locations, route segments and QR marker codes."

    @transaction.atomic
    def handle(self, *args, **options):
        RouteSegment.objects.all().delete()
        Location.objects.all().delete()

        index = {}
        for code, name_en, name_bn, map_label, kind, block, x, y, qr in LOCATIONS:
            index[code] = Location.objects.create(
                code=code,
                name_en=name_en,
                name_bn=name_bn,
                map_label=map_label,
                kind=kind,
                block=block,
                x=x,
                y=y,
                qr_code=qr,
            )

        for from_code, to_code, instr_en, instr_bn, distance in SEGMENTS:
            RouteSegment.objects.create(
                from_location=index[from_code],
                to_location=index[to_code],
                instruction_en=instr_en,
                instruction_bn=instr_bn,
                distance_m=distance,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(LOCATIONS)} locations, {len(SEGMENTS)} route segments.")
        )
