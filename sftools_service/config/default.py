from sftools_service.domain.enums.building_category import BuildingCategory
from sftools_service.domain.enums.item_categories import ItemCategory

NAME_TO_BUILDING_CATEGORY_MAP = {
    'Extraction': BuildingCategory.EXTRACTION,
    'Production': BuildingCategory.PRODUCTION,
    'Generators': BuildingCategory.GENERATORS,
    'Special': BuildingCategory.SPECIAL,
    'Workstations': BuildingCategory.WORKSTATIONS,
    'Storage': BuildingCategory.STORAGE,
    'Docking stations': BuildingCategory.DOCKING,
    'Towers': BuildingCategory.TOWERS,
}

NAME_TO_ITEM_CATEGORY_MAP = {
    'Ores': ItemCategory.ORES,
    'Ingots': ItemCategory.INGOTS,
    'Minerals': ItemCategory.MINERALS,
    'Liquids': ItemCategory.LIQUIDS,
    'Gas': ItemCategory.GAS,
    'Standard Parts': ItemCategory.STANDARD,
    'Industrial Parts': ItemCategory.INDUSTRIAL,
    'Electronics': ItemCategory.ELECTRONICS,
    'Communications': ItemCategory.COMMUNICATIONS,
    'Containers': ItemCategory.CONTAINERS,
    'Fuels': ItemCategory.FUELS,
    'Consumed': ItemCategory.CONSUMED,
    'Nuclear': ItemCategory.NUCLEAR,
    'Waste': ItemCategory.WASTE,
    'Special': ItemCategory.SPECIAL,
}
