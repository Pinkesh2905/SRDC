from django.db import models
import copy
from customers.models import Customer

class GarmentCategory(models.TextChoices):
    SHIRT = 'shirt', 'Shirt'
    PANT = 'pant', 'Pant'
    INDOWESTERN = 'indowestern', 'Indowestern'
    TWO_PIECE_INDOWESTERN = '2pc_indowestern', '2-Piece Indowestern'
    SHERVANI = 'shervani', 'Shervani'
    JODHPURI = 'jodhpuri', 'Jodhpuri'
    OPEN_JODHPURI = 'open_jodhpuri', 'Open Jodhpuri'
    JABBHA = 'jabbha', 'Jabbha'
    TWO_PIECE_SHERVANI = '2pc_shervani', '2-Piece Shervani'
    TWO_PIECE_JODHPURI = '2pc_jodhpuri', '2-Piece Jodhpuri'
    LENGHO = 'lengho', 'Lengho'

GARMENT_PARAMETERS = {
    'shirt': ['Length', 'Chest', 'Shoulder', 'Sleeve', 'Wrist', 'Neck', 'Front1', 'Front2', 'Front3'],
    'pant': ['Length', 'Waist', 'Hips', 'Thighs', 'Knee', 'Ankle', 'Round'],
    'indowestern': ['Length', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    '2pc_indowestern': ['Length1', 'Length2', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    'shervani': ['Length', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    'jodhpuri': ['Length', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    'open_jodhpuri': ['Length', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    'jabbha': ['Length', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    '2pc_shervani': ['Length1', 'Length2', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    '2pc_jodhpuri': ['Length1', 'Length2', 'Chest', 'Stomach', 'Hips (Seat)', 'Shoulder', 'Sleeve', 'Wrist', 'Neck'],
    'lengho': ['Length', 'Waist', 'Hips', 'Thighs', 'Knee', 'Ankle', 'Round'],
}

class CustomGarmentCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CustomGarmentParameter(models.Model):
    category_name = models.CharField(max_length=50)
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = ('category_name', 'name')

    def __str__(self):
        return f"{self.category_name} - {self.name}"

def get_all_garment_categories():
    base_choices = list(GarmentCategory.choices)
    custom_categories = CustomGarmentCategory.objects.all()
    for cat in custom_categories:
        slug = cat.name.lower().replace(' ', '_')
        base_choices.append((slug, cat.name))
    return base_choices

def get_all_garment_parameters():
    params = copy.deepcopy(GARMENT_PARAMETERS)
    for cp in CustomGarmentParameter.objects.all():
        if cp.category_name not in params:
            params[cp.category_name] = []
        params[cp.category_name].append(cp.name)
    return params


class Measurement(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='measurements')
    garment_category = models.CharField(max_length=50)
    values = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    is_sample_product = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        pass

    def __str__(self):
        cat_dict = dict(get_all_garment_categories())
        display = cat_dict.get(self.garment_category, self.garment_category.title())
        return f"{self.customer.full_name} - {display}"
