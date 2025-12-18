"""
Item data normalizer for cleaning and classifying inventory items.
Handles messy user input with typos and inconsistent formatting.
"""
import re
from dataclasses import dataclass
from config import logger


@dataclass
class NormalizedItem:
    """Represents a normalized item with cleaned data."""
    code: str
    name: str
    itemType: str
    unit: str | None


class ItemNormalizer:
    """Normalizes and classifies inventory items based on code/name patterns."""

    # Common typos and aliases (lowercase) -> canonical form
    TYPO_FIXES = {
        # R2DX variants - users type all kinds of stuff
        'riidx': 'r2dx',
        'r2d': 'r2dx',
        'rdx': 'r2dx',
        'r2xd': 'r2dx',
        'ridx': 'r2dx',
        'riix': 'r2dx',
        'r11dx': 'r2dx',
        # KSD variants
        'kds': 'ksd',
        'skd': 'ksd',
        # KMD variants
        'kdm': 'kmd',
        'mkd': 'kmd',
    }

    # Walking floor model patterns (checked BEFORE general type rules)
    WALKING_FLOOR_MODELS = [
        (r'(ksd|kds|skd)', 'walking_floor_ksd'),
        (r'(kmd|kdm|mkd)', 'walking_floor_kmd'),
        (r'(r2dx|riidx|r2d|rdx|ridx|riix|r11dx)', 'walking_floor_r2dx'),
    ]

    # Item type classification rules: (pattern, type)
    # Order matters - first match wins
    # Note: patterns match against "code name" combined string (no anchors!)
    TYPE_RULES = [
        # Burning fuels - match code OR name patterns
        (r'\bbadieu\b', 'burning_fuel'),
        (r'bã\s*điều', 'burning_fuel'),
        (r'\bdau\b', 'burning_fuel'),  # code "DAU"
        (r'd[aầ]u\s*do', 'burning_fuel'),  # name "Dầu DO"
        (r'\bthan\b', 'burning_fuel'),
        (r'trauvien', 'burning_fuel'),
        (r'trấu\s*viên', 'burning_fuel'),
        
        # Hydraulic/Engine Oil (must come BEFORE hydraulic_pump to catch "Hydraulic Oil")
        (r'nh[oớ]t', 'hydraulic_oil'),  # "nhớt" - Vietnamese for lubricant/oil
        (r'hydraulic.*oil|oil.*hydraulic', 'hydraulic_oil'),
        (r'engine.*oil|oil.*engine', 'hydraulic_oil'),
        (r'lubricant', 'hydraulic_oil'),
        
        # Hydraulic pumps (specific pump patterns only)
        # Note: "thuỷ" can be spelled as thủy (ủ+y) or thuỷ (u+ỷ)
        (r'b[oơ]m.*th[uủ][yỷ].*l[uự]c', 'hydraulic_pump'),
        (r'hydraulic.*pump|pump.*hydraulic', 'hydraulic_pump'),
        
        # Controllers
        (r'h[oộ]p.*[đd]i[eề]u.*khi[eể]n', 'controller'),
        (r'controller', 'controller'),
        
        # Walking floor - generic fallback (sàn di động without model)
        (r'sàn.*di.*[đd][oộ]ng', 'walking_floor'),
        (r'walking.*floor', 'walking_floor'),
        (r'\bkeith\b', 'walking_floor'),
        
        # Aluminum
        (r'nh[oô]m', 'aluminum'),
        (r'aluminum|aluminium', 'aluminum'),
        
        # Steel types (order matters - specific before general)
        (r'th[eé]p.*kh[oô]ng.*g[iỉ]', 'stainless_steel'),
        (r'stainless', 'stainless_steel'),
        (r'th[eé]p.*h[oộ]p|thep.*hop', 'steel_box'),
        (r'th[eé]p.*[oố]ng|thep.*ong', 'steel_pipe'),
        (r'th[eé]p.*t[aấ]m|thep.*tam', 'steel_plate'),
        (r'th[eé]p.*vu[oô]ng|thep.*vuong', 'steel_square'),
        (r'th[eé]p.*u\d|thepu|thép\s*u', 'steel_u'),
        (r'th[eé]p.*i\d|thepi', 'steel_i'),
        (r'\bthep\b|\bthép\b', 'steel'),
        
        # Galvanized sheet
        (r't[oô]n.*m[aạ].*k[eẽ]m', 'galvanized_sheet'),
        (r'galvanized', 'galvanized_sheet'),
        
        # Containers
        (r'v[oỏ].*container', 'container'),
        (r'\bcontainer\b', 'container'),
    ]

    # Default units for item types (when unit is NULL/missing)
    DEFAULT_UNITS = {
        'walking_floor': 'set',
        'walking_floor_ksd': 'set',
        'walking_floor_kmd': 'set',
        'walking_floor_r2dx': 'set',
        'container': 'set',
        'controller': 'set',
        'hydraulic_pump': 'pcs',
        'hydraulic_oil': 'barrel',
    }

    # Unit normalization map (handles typos too)
    UNIT_MAP = {
        'kg': 'kg',
        'kilo': 'kg',
        'kilogram': 'kg',
        'lít': 'L',
        'lit': 'L',
        'liter': 'L',
        'litre': 'L',
        'l': 'L',
        'cái': 'pcs',
        'cai': 'pcs',
        'chiếc': 'pcs',
        'chiec': 'pcs',
        'pcs': 'pcs',
        'piece': 'pcs',
        'bộ': 'set',
        'bo': 'set',
        'set': 'set',
        'mét': 'm',
        'met': 'm',
        'meter': 'm',
        'm': 'm',
        'phuy': 'barrel',  # Vietnamese for drum/barrel/can
        'can': 'can',
        'thùng': 'box',
        'thung': 'box',
    }

    @classmethod
    def _fixTypos(cls, text: str) -> str:
        """
        Fix common typos in user input.
        Replaces known typos with canonical forms.
        """
        if not text:
            return text
        
        words = text.lower().split('_')
        fixedWords = []
        
        for word in words:
            # Check each word for typos
            fixed = cls.TYPO_FIXES.get(word, word)
            fixedWords.append(fixed)
        
        return '_'.join(fixedWords)

    @staticmethod
    def normalizeCode(code: str) -> str:
        """
        Normalize item code by removing problematic characters.
        Handles messy user input with quotes, spaces, special chars.
        """
        if not code:
            return ""
        
        # Strip whitespace
        code = code.strip()
        
        # Remove quotes (single, double, smart quotes)
        code = re.sub(r'["\'"\u2018\u2019\u201c\u201d]', '', code)
        
        # Replace spaces and multiple underscores with single underscore
        code = re.sub(r'[\s_]+', '_', code)
        
        # Remove leading/trailing underscores
        code = code.strip('_')
        
        return code

    @staticmethod
    def normalizeName(name: str) -> str:
        """
        Normalize item name by cleaning up whitespace and formatting.
        """
        if not name:
            return ""
        
        # Strip and normalize whitespace
        name = ' '.join(name.split())
        
        # Remove leading/trailing quotes (including smart quotes)
        name = re.sub(r'^["\'"\u2018\u2019\u201c\u201d]+|["\'"\u2018\u2019\u201c\u201d]+$', '', name)
        
        return name

    @classmethod
    def normalizeUnit(cls, unit: str | None) -> str | None:
        """
        Normalize unit to standard format.
        Returns None if unit is invalid or NULL.
        """
        if not unit:
            return None
        
        unitClean = unit.strip()
        
        # Check for null-like values
        if unitClean.upper() in ('NULL', 'NONE', 'N/A', 'NA', '-', ''):
            return None
        
        unitLower = unitClean.lower()
        return cls.UNIT_MAP.get(unitLower, unitClean)

    @classmethod
    def classifyType(cls, code: str, name: str) -> str:
        """
        Classify item type based on code and name patterns.
        Handles typos and user input variations.
        Returns 'other' if no pattern matches.
        """
        # Fix typos first
        fixedCode = cls._fixTypos(code)
        fixedName = cls._fixTypos(name.replace(' ', '_'))
        
        # Combine for pattern matching
        searchText = f"{fixedCode} {fixedName}".lower()
        
        # Check walking floor models first (more specific)
        for pattern, itemType in cls.WALKING_FLOOR_MODELS:
            if re.search(pattern, searchText, re.IGNORECASE):
                return itemType
        
        # Check general type rules
        for pattern, itemType in cls.TYPE_RULES:
            if re.search(pattern, searchText, re.IGNORECASE):
                return itemType
        
        return 'other'

    @classmethod
    def normalize(cls, code: str, name: str, unit: str | None) -> NormalizedItem:
        """
        Normalize an item's code, name, unit, and classify its type.
        Applies default units for certain item types when unit is missing.
        Returns a NormalizedItem dataclass.
        """
        normalizedCode = cls.normalizeCode(code)
        normalizedName = cls.normalizeName(name)
        normalizedUnit = cls.normalizeUnit(unit)
        itemType = cls.classifyType(normalizedCode, normalizedName)
        
        # Apply default unit if missing and type has a default
        if normalizedUnit is None and itemType in cls.DEFAULT_UNITS:
            normalizedUnit = cls.DEFAULT_UNITS[itemType]
            logger.debug(f"Applied default unit '{normalizedUnit}' for type '{itemType}'")
        
        logger.debug(f"Normalized: {code} -> {normalizedCode} (type: {itemType})")
        
        return NormalizedItem(
            code=normalizedCode,
            name=normalizedName,
            itemType=itemType,
            unit=normalizedUnit,
        )


def main():
    """Test normalizer with sample data including typos."""
    testItems = [
        # Burning fuels
        ("BADIEU", "Bã điều", "kg"),
        ("DAU", "Dầu DO", "Lít"),  # Should be burning_fuel!
        ("THAN", "Than", "kg"),
        ("trauvien", "Trấu viên", "kg"),
        
        # Hydraulic oil (should NOT be hydraulic_pump!)
        ("Nhớt Hydraulic Oil 68 (BP) - 209L", "Nhớt Hydraulic Oil 68 (BP) - 209L", "Phuy"),
        ("Engine Oil 10W40", "Engine Oil 10W40", "barrel"),
        ("Lubricant SAE 30", "Lubricant SAE 30", None),  # Should get default 'barrel'
        
        # Equipment (should NOT be 'other')
        ("Bơm thuỷ lực", "Bơm thuỷ lực", "Cái"),
        ("hộp điều khiển chế tạo", "hộp điều khiển chế tạo", "Bộ"),
        
        # Walking floor - KMD (NULL unit should become 'set')
        ("KMD300 24X97MM", "Sàn di động KMD", "NULL"),
        
        # Walking floor - KSD (with typos)
        ("KSD 4.25", "Keith Walking Floor KSD", "set"),
        ("kds_test", "KDS typo test", "bộ"),
        ("ksd_107243803660_05062025", "Sàn di động KSD", None),  # NULL unit
        
        # Walking floor - R2DX (with typos!)
        ("R2DX 4.0", "Sàn di động R2DX", "Bộ"),
        ("r2dx4_107243803660", "R2DX model", "set"),
        ("RIIDX_test", "RIIDX typo -> R2DX", "set"),
        ("riidx_user_input", "User typed riidx", "NULL"),  # Should get default 'set'
        
        # Steel types
        ("thephop", "THÉP HỘP", "kg"),
        ("thep tam 12 ly", "Thép tấm 12 ly", "kg"),
        
        # Others
        ("Nhôm thanh #000", "Nhôm thanh #000", "kg"),
        ("Vỏ container 20 feet", "Vỏ container 20 feet", "Bộ"),
    ]
    
    print("\n" + "=" * 80)
    print("Item Normalizer Test (with typo handling & default units)")
    print("=" * 80)
    
    for code, name, unit in testItems:
        result = ItemNormalizer.normalize(code, name, unit)
        unitDisplay = f"'{result.unit}'" if result.unit else "NULL"
        print(f"\nInput:  code='{code}', unit='{unit}'")
        print(f"Output: type='{result.itemType}', unit={unitDisplay}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
