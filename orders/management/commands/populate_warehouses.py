from django.core.management.base import BaseCommand
from orders.models import Warehouse
from accounts.models import Address, User
from decimal import Decimal
from django.db import transaction

class Command(BaseCommand):
    help = "Populates the Warehouse model with all Egyptian governorates."

    def handle(self, *args, **options):
        # List of all 27 Egyptian governorates
        egyptian_governorates = [
            "Alexandria", "Aswan", "Asyut", "Beheira", "Beni Suef", "Cairo", 
            "Dakahlia", "Damietta", "Faiyum", "Gharbia", "Giza", "Ismailia", 
            "Kafr El Sheikh", "Luxor", "Matrouh", "Minya", "Monufia", "New Valley", 
            "North Sinai", "Port Said", "Qalyubia", "Qena", "Red Sea", "Sharqia", 
            "Sohag", "South Sinai", "Suez"
        ]

        # Use a transaction to ensure all or none of the objects are created
        with transaction.atomic():
            self.stdout.write("Starting to populate warehouses for all Egyptian governorates...")
            
            # Get or create the placeholder user for warehouse addresses
            # Assuming you have a user with this email for administrative addresses
            craft_user, created = User.objects.get_or_create(
                email="CraftEG@craft.com", 
                defaults={'first_name': 'Craft', 'last_name': 'User'}
            )
            
            for governorate in egyptian_governorates:
                warehouse_name = f"{governorate}"

                # Check if the warehouse already exists to prevent duplicates
                if Warehouse.objects.filter(name=warehouse_name).exists():
                    self.stdout.write(self.style.WARNING(f"Warehouse for {governorate} already exists. Skipping."))
                    continue

                # Create a placeholder address for the warehouse
                address, created = Address.objects.get_or_create(
                    user=craft_user,
                    State=governorate,
                    defaults={
                        'BuildingNO': "10",
                        'Street': f"{governorate} Main Street",
                        'City': governorate
                    }
                )

                # Create the Warehouse instance with the provided data
                Warehouse.objects.create(
                    name=warehouse_name,
                    Address=address,
                    contact_person="Waleed Darwesh",
                    contact_phone="01101114638",
                    delivery_fee=Decimal('50.00')
                )
                self.stdout.write(self.style.SUCCESS(f"Successfully created warehouse for {governorate}."))

        self.stdout.write(self.style.SUCCESS("\nWarehouse population script finished."))
