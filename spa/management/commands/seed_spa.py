"""Management command to seed demo spa data."""
from django.core.management.base import BaseCommand

from spa.models import Service, ServiceCategory, Therapist


SERVICES = [
    {
        "name": "Swedish Massage",
        "description": "A gentle full-body massage using long, flowing strokes to relax muscles and improve circulation. Perfect for first-time visitors.",
        "duration_minutes": 60,
        "price": "850000",
        "category": ServiceCategory.MASSAGE,
        "emoji": "💆",
    },
    {
        "name": "Deep Tissue Massage",
        "description": "Targets deeper layers of muscle and connective tissue to relieve chronic tension and pain. Recommended for athletic recovery.",
        "duration_minutes": 90,
        "price": "1200000",
        "category": ServiceCategory.MASSAGE,
        "emoji": "💪",
    },
    {
        "name": "Hot Stone Massage",
        "description": "Smooth, heated basalt stones are placed on key points of the body to relieve tension and balance energy.",
        "duration_minutes": 75,
        "price": "1100000",
        "category": ServiceCategory.MASSAGE,
        "emoji": "🪨",
    },
    {
        "name": "Hydrating Facial",
        "description": "A deeply nourishing facial treatment using hyaluronic acid and vitamin C serums. Leaves skin glowing and refreshed.",
        "duration_minutes": 60,
        "price": "950000",
        "category": ServiceCategory.FACIAL,
        "emoji": "🌸",
    },
    {
        "name": "Anti-Aging Facial",
        "description": "Advanced facial using retinol and peptide-rich formulations to reduce fine lines and restore elasticity.",
        "duration_minutes": 75,
        "price": "1300000",
        "category": ServiceCategory.FACIAL,
        "emoji": "✨",
    },
    {
        "name": "Body Wrap",
        "description": "A luxurious full-body treatment using mineral-rich mud and essential oils to detoxify and soften the skin.",
        "duration_minutes": 90,
        "price": "1400000",
        "category": ServiceCategory.BODY,
        "emoji": "🫧",
    },
    {
        "name": "Exfoliating Body Scrub",
        "description": "A sea salt and coconut oil scrub that buffs away dead skin cells, revealing silky-smooth skin beneath.",
        "duration_minutes": 45,
        "price": "750000",
        "category": ServiceCategory.BODY,
        "emoji": "🌿",
    },
    {
        "name": "Luxury Manicure",
        "description": "A full manicure with cuticle care, nail shaping, hand massage, and your choice of polish.",
        "duration_minutes": 45,
        "price": "550000",
        "category": ServiceCategory.NAILS,
        "emoji": "💅",
    },
    {
        "name": "Gel Pedicure",
        "description": "Relaxing foot soak, exfoliation, massage, and long-lasting gel polish application.",
        "duration_minutes": 60,
        "price": "700000",
        "category": ServiceCategory.NAILS,
        "emoji": "🦶",
    },
    {
        "name": "Aromatherapy Session",
        "description": "A personalised wellness journey combining breathwork, essential oil diffusion, and guided relaxation.",
        "duration_minutes": 60,
        "price": "900000",
        "category": ServiceCategory.WELLNESS,
        "emoji": "🕯️",
    },
]

THERAPISTS = [
    {
        "name": "Amara Johnson",
        "bio": "Certified massage therapist with 12 years of experience specialising in Swedish and deep tissue techniques. Amara's gentle yet effective approach has earned her a loyal following.",
        "service_names": ["Swedish Massage", "Deep Tissue Massage", "Hot Stone Massage"],
    },
    {
        "name": "Lena Park",
        "bio": "Skincare specialist and esthetician with a passion for holistic beauty. Lena holds advanced certifications in anti-aging and corrective treatments.",
        "service_names": ["Hydrating Facial", "Anti-Aging Facial", "Exfoliating Body Scrub"],
    },
    {
        "name": "Marco Rivera",
        "bio": "Sports massage therapist and wellness coach. Marco works extensively with athletes and active individuals to optimise recovery and performance.",
        "service_names": ["Deep Tissue Massage", "Hot Stone Massage", "Aromatherapy Session"],
    },
    {
        "name": "Sophie Chen",
        "bio": "Nail artist and luxury beauty technician. Sophie's meticulous attention to detail and artistic flair make every appointment a creative experience.",
        "service_names": ["Luxury Manicure", "Gel Pedicure", "Hydrating Facial"],
    },
    {
        "name": "Priya Sharma",
        "bio": "Ayurvedic wellness practitioner and body treatment specialist with training from the Kerala Ayurveda Academy.",
        "service_names": ["Aromatherapy Session", "Body Wrap", "Swedish Massage"],
    },
]


class Command(BaseCommand):
    help = "Seeds the database with demo spa services and therapists."

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding spa data...")

        # Create services
        service_map = {}
        for data in SERVICES:
            service, created = Service.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "duration_minutes": data["duration_minutes"],
                    "price": data["price"],
                    "category": data["category"],
                    "emoji": data["emoji"],
                },
            )
            service_map[service.name] = service
            action = "Created" if created else "Exists"
            self.stdout.write(f"  {action}: {service.name}")

        # Create therapists
        for data in THERAPISTS:
            therapist, created = Therapist.objects.get_or_create(
                name=data["name"],
                defaults={"bio": data["bio"]},
            )
            # Assign specialties
            for service_name in data["service_names"]:
                if service_name in service_map:
                    therapist.specialties.add(service_map[service_name])
            action = "Created" if created else "Exists"
            self.stdout.write(f"  {action}: {therapist.name}")

        self.stdout.write(self.style.SUCCESS("\nSpa seed complete!"))
        self.stdout.write(f"   Services: {Service.objects.count()}")
        self.stdout.write(f"   Therapists: {Therapist.objects.count()}")
        self.stdout.write(f"\n   Visit: http://127.0.0.1:8000/spa/")
