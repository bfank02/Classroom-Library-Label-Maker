"""Generate ``samples/Teacher Demo Library.xlsx`` for manual QA / demos.

Creates ~180 classroom-library rows with a mix of valid ISBNs, blank ISBNs,
invalid ISBNs, duplicates, and intentionally ambiguous titles.

Run from ``barcode_generator/``::

    python ../samples/_generate_teacher_demo_library.py

Or with the package on ``PYTHONPATH`` / editable install.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from classroom_library_label_maker.constants import (
    DEFAULT_WORKBOOK_COLUMN_AUTHOR,
    DEFAULT_WORKBOOK_COLUMN_COPIES,
    DEFAULT_WORKBOOK_COLUMN_ISBN,
    DEFAULT_WORKBOOK_COLUMN_TITLE,
    DEFAULT_WORKBOOK_SHEET_NAME,
)
from classroom_library_label_maker.services.isbn_validator import IsbnValidator

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parent / "Teacher Demo Library.xlsx"

# Verified ISBN-13 classroom titles (isbn, title, author, copies).
_VERIFIED: list[tuple[str, str, str, int]] = [
    ("9780064400558", "Charlotte's Web", "E. B. White", 3),
    ("9780394800011", "The Cat in the Hat", "Dr. Seuss", 4),
    ("9780394800165", "Green Eggs and Ham", "Dr. Seuss", 3),
    ("9780394839127", "Oh, the Places You'll Go!", "Dr. Seuss", 2),
    ("9780399226908", "The Very Hungry Caterpillar", "Eric Carle", 4),
    ("9780399214578", "Owl Moon", "Jane Yolen", 2),
    ("9780694003617", "Goodnight Moon", "Margaret Wise Brown", 3),
    ("9780060256654", "The Giving Tree", "Shel Silverstein", 2),
    ("9780399216190", "Brown Bear, Brown Bear, What Do You See?", "Bill Martin Jr.", 4),
    ("9780152024284", "Chicka Chicka Boom Boom", "Bill Martin Jr.", 3),
    ("9780140501827", "The Snowy Day", "Ezra Jack Keats", 2),
    ("9780670889174", "The Rainbow Fish", "Marcus Pfister", 2),
    ("9780399213014", "The Polar Express", "Chris Van Allsburg", 2),
    ("9780399230134", "Click, Clack, Moo: Cows That Type", "Doreen Cronin", 2),
    ("9780439080231", "Don't Let the Pigeon Drive the Bus!", "Mo Willems", 3),
    ("9780763609764", "Guess How Much I Love You", "Sam McBratney", 2),
    ("9780399257742", "Llama Llama Red Pajama", "Anna Dewdney", 3),
    ("9780399246531", "Skippyjon Jones", "Judy Schachner", 2),
    ("9780064440202", "Frog and Toad Are Friends", "Arnold Lobel", 4),
    ("9780064440233", "Frog and Toad Together", "Arnold Lobel", 3),
    ("9780064440042", "Little Bear", "Else Holmelund Minarik", 2),
    ("9780064440226", "Owl at Home", "Arnold Lobel", 2),
    ("9780689810176", "Henry and Mudge: The First Book", "Cynthia Rylant", 3),
    ("9780689816116", "Henry and Mudge and the Happy Cat", "Cynthia Rylant", 2),
    ("9780689802188", "Mr. Putter & Tabby Pour the Tea", "Cynthia Rylant", 2),
    ("9780763645045", "Mercy Watson to the Rescue", "Kate DiCamillo", 3),
    ("9780763650124", "Mercy Watson Goes for a Ride", "Kate DiCamillo", 2),
    ("9781423133087", "We Are in a Book!", "Mo Willems", 4),
    ("9781423119913", "I Will Surprise My Friend!", "Mo Willems", 3),
    ("9781423109624", "There Is a Bird on Your Head!", "Mo Willems", 3),
    ("9780064441551", "Amelia Bedelia", "Peggy Parish", 3),
    ("9780545215787", "Clifford the Big Red Dog", "Norman Bridwell", 4),
    ("9780545215831", "Clifford's Good Deeds", "Norman Bridwell", 2),
    ("9780061906220", "Pete the Cat: I Love My White Shoes", "Eric Litwin", 4),
    ("9780062304186", "Pete the Cat: Rocking in My School Shoes", "Eric Litwin", 3),
    ("9780062110589", "Pete the Cat and His Four Groovy Buttons", "Eric Litwin", 3),
    ("9780062675279", "Pete the Cat: Big Easter Adventure", "James Dean", 2),
    ("9780316111164", "Arthur's Eyes", "Marc Brown", 2),
    ("9780316111195", "Arthur's Teacher Trouble", "Marc Brown", 2),
    ("9780316110693", "Arthur Meets the President", "Marc Brown", 1),
    ("9780307119391", "Just Me and My Mom", "Mercer Mayer", 3),
    ("9780307125835", "I Was So Mad", "Mercer Mayer", 2),
    ("9780307118424", "Just Go to Bed", "Mercer Mayer", 2),
    ("9780307119384", "Just a Mess", "Mercer Mayer", 2),
    ("9780679824114", "Dinosaurs Before Dark", "Mary Pope Osborne", 4),
    ("9780679824121", "The Knight at Dawn", "Mary Pope Osborne", 3),
    ("9780679824138", "Mummies in the Morning", "Mary Pope Osborne", 3),
    ("9780679824145", "Pirates Past Noon", "Mary Pope Osborne", 2),
    ("9780679894063", "Tonight on the Titanic", "Mary Pope Osborne", 2),
    ("9780679826422", "Junie B. Jones and the Stupid Smelly Bus", "Barbara Park", 4),
    ("9780679843658", "Junie B. Jones and a Little Monkey Business", "Barbara Park", 3),
    ("9780679843665", "Junie B. Jones and Her Big Fat Mouth", "Barbara Park", 3),
    ("9780679864707", "Junie B. Jones Is Not a Crook", "Barbara Park", 2),
    ("9780810993136", "Diary of a Wimpy Kid", "Jeff Kinney", 5),
    ("9780810981249", "Diary of a Wimpy Kid: Rodrick Rules", "Jeff Kinney", 3),
    ("9780810981263", "Diary of a Wimpy Kid: The Last Straw", "Jeff Kinney", 2),
    ("9780545581608", "Dog Man", "Dav Pilkey", 5),
    ("9780545935203", "Dog Man: Unleashed", "Dav Pilkey", 3),
    ("9780545935210", "Dog Man: A Tale of Two Kitties", "Dav Pilkey", 3),
    ("9780439377119", "The Adventures of Captain Underpants", "Dav Pilkey", 3),
    ("9780142410349", "The Tale of Despereaux", "Kate DiCamillo", 2),
    ("9780142407332", "Because of Winn-Dixie", "Kate DiCamillo", 3),
    ("9780140328721", "Matilda", "Roald Dahl", 3),
    ("9780142410318", "The BFG", "Roald Dahl", 2),
    ("9780142410356", "James and the Giant Peach", "Roald Dahl", 2),
    ("9780142410332", "Charlie and the Chocolate Factory", "Roald Dahl", 3),
    ("9780439708180", "Harry Potter and the Sorcerer's Stone", "J. K. Rowling", 4),
    ("9780439064873", "Harry Potter and the Chamber of Secrets", "J. K. Rowling", 2),
    ("9780439136365", "Harry Potter and the Prisoner of Azkaban", "J. K. Rowling", 2),
    ("9780439358064", "Harry Potter and the Order of the Phoenix", "J. K. Rowling", 1),
    ("9780064403375", "Number the Stars", "Lois Lowry", 2),
    ("9780545044257", "The Lightning Thief", "Rick Riordan", 3),
    ("9781423103349", "The Sea of Monsters", "Rick Riordan", 2),
    ("9780439023481", "The Hunger Games", "Suzanne Collins", 2),
    ("9780064404778", "The Lion, the Witch and the Wardrobe", "C. S. Lewis", 2),
    ("9780064471046", "Prince Caspian", "C. S. Lewis", 1),
    ("9780062024022", "Wonder", "R. J. Palacio", 2),
    ("9780312623555", "Fish in a Tree", "Lynda Mullaly Hunt", 1),
    ("9780142401101", "Tales of a Fourth Grade Nothing", "Judy Blume", 2),
    ("9780142408810", "Superfudge", "Judy Blume", 1),
    ("9780439139601", "Holes", "Louis Sachar", 2),
    ("9780440414803", "Bud, Not Buddy", "Christopher Paul Curtis", 1),
    ("9780439120425", "The Bad Beginning", "Lemony Snicket", 2),
    ("9781426313714", "National Geographic Kids: Weather", "Kathy Furgang", 2),
    ("9781426313479", "National Geographic Kids: Sharks!", "Anne Schreiber", 3),
    ("9781426314421", "National Geographic Kids: Dinosaurs", "Kathleen Weidner Zoehfeld", 2),
    ("9781426315053", "National Geographic Kids: Planets", "Elizabeth Carney", 2),
    ("9781426324390", "National Geographic Kids: Spiders", "Laura Marsh", 1),
    ("9780545685153", "Who Was Rosa Parks?", "Yona Zeldis McDonough", 2),
    ("9780448459714", "Who Was Albert Einstein?", "Jess Brallier", 2),
    ("9780448439013", "Who Was Harriet Tubman?", "Yona Zeldis McDonough", 1),
    ("9780448428895", "Who Was Walt Disney?", "Whitney Stewart", 1),
    ("9780448439044", "Who Was Dr. Seuss?", "Janet Pascal", 2),
    ("9781338236668", "I Survived the American Revolution, 1776", "Lauren Tarshis", 2),
    ("9780545206969", "I Survived Hurricane Katrina, 2005", "Lauren Tarshis", 2),
    ("9780064450157", "From Seed to Plant", "Gail Gibbons", 2),
    ("9780823419975", "Apples", "Gail Gibbons", 1),
    ("9780823421992", "The Pumpkin Book", "Gail Gibbons", 2),
    ("9780823416332", "Tornadoes!", "Gail Gibbons", 1),
    ("9780823430543", "Hurricanes!", "Gail Gibbons", 1),
]

# Clear title/author pairs for blank-ISBN enrichment (no ISBN in workbook).
_BLANK_LOOKUP: list[tuple[str, str, int]] = [
    ("Where the Wild Things Are", "Maurice Sendak", 3),
    ("The Miraculous Journey of Edward Tulane", "Kate DiCamillo", 2),
    ("Stuart Little", "E. B. White", 2),
    ("The Trumpet of the Swan", "E. B. White", 1),
    ("Frindle", "Andrew Clements", 3),
    ("Sarah, Plain and Tall", "Patricia MacLachlan", 2),
    ("Bridge to Terabithia", "Katherine Paterson", 2),
    ("Esperanza Rising", "Pam Muñoz Ryan", 2),
    ("Catching Fire", "Suzanne Collins", 2),
    ("Mockingjay", "Suzanne Collins", 1),
    ("Knuffle Bunny: A Cautionary Tale", "Mo Willems", 2),
    ("My Friend Is Sad", "Mo Willems", 2),
    ("Poppleton", "Cynthia Rylant", 2),
    ("The Stories Julian Tells", "Ann Cameron", 1),
    ("I Survived the Sinking of the Titanic, 1912", "Lauren Tarshis", 3),
    ("Captain Underpants and the Attack of the Talking Toilets", "Dav Pilkey", 2),
    ("Amelia Bedelia Unleashed", "Herman Parish", 2),
    ("No More Monsters for Me!", "Peggy Parish", 1),
    ("If You Give a Mouse a Cookie", "Laura Numeroff", 4),
    ("If You Give a Pig a Pancake", "Laura Numeroff", 2),
    ("The Kissing Hand", "Audrey Penn", 3),
    ("Corduroy", "Don Freeman", 3),
    ("Madeline", "Ludwig Bemelmans", 2),
    ("Make Way for Ducklings", "Robert McCloskey", 2),
    ("Blueberries for Sal", "Robert McCloskey", 1),
    ("Strega Nona", "Tomie dePaola", 2),
    ("The Recess Queen", "Alexis O'Neill", 2),
    ("Enemy Pie", "Derek Munson", 1),
    ("Those Shoes", "Maribeth Boelts", 1),
    ("Last Stop on Market Street", "Matt de la Peña", 2),
    ("The Day the Crayons Quit", "Drew Daywalt", 3),
    ("Dragons Love Tacos", "Adam Rubin", 2),
    ("The Book with No Pictures", "B. J. Novak", 2),
    ("Press Here", "Hervé Tullet", 2),
    ("A Sick Day for Amos McGee", "Philip C. Stead", 1),
    ("Extra Yarn", "Mac Barnett", 1),
    ("Sam and Dave Dig a Hole", "Mac Barnett", 1),
    ("Ada Twist, Scientist", "Andrea Beaty", 2),
    ("Rosie Revere, Engineer", "Andrea Beaty", 2),
    ("Iggy Peck, Architect", "Andrea Beaty", 1),
    ("The One and Only Ivan", "Katherine Applegate", 2),
    ("Wishtree", "Katherine Applegate", 1),
    ("Front Desk", "Kelly Yang", 1),
    ("New Kid", "Jerry Craft", 2),
    ("A Boy Called Bat", "Elana K. Arnold", 1),
]

# Titles likely to yield multiple Google Books editions (blank ISBN).
_AMBIGUOUS: list[tuple[str, str, int]] = [
    ("Magic Tree House", "Mary Pope Osborne", 2),
    ("Pete the Cat", "James Dean", 3),
    ("National Geographic Readers", "National Geographic Kids", 2),
    ("Frog and Toad", "Arnold Lobel", 2),
    ("Little Critter", "Mercer Mayer", 3),
    ("Clifford", "Norman Bridwell", 2),
    ("Junie B. Jones", "Barbara Park", 2),
    ("Amelia Bedelia", "Peggy Parish", 2),
    ("Arthur", "Marc Brown", 2),
]

# Extra titles that get synthetic-but-valid ISBN-13s to reach ~60% valid rows.
_SYNTHETIC_TITLES: list[tuple[str, str, int]] = [
    ("The Boxcar Children", "Gertrude Chandler Warner", 2),
    ("Encyclopedia Brown, Boy Detective", "Donald J. Sobol", 1),
    ("Ramona Quimby, Age 8", "Beverly Cleary", 2),
    ("Beezus and Ramona", "Beverly Cleary", 1),
    ("The Mouse and the Motorcycle", "Beverly Cleary", 2),
    ("Ralph S. Mouse", "Beverly Cleary", 1),
    ("Sideways Stories from Wayside School", "Louis Sachar", 2),
    ("Wayside School Is Falling Down", "Louis Sachar", 1),
    ("There's a Boy in the Girls' Bathroom", "Louis Sachar", 1),
    ("The Giver", "Lois Lowry", 2),
    ("Gathering Blue", "Lois Lowry", 1),
    ("A Wrinkle in Time", "Madeleine L'Engle", 2),
    ("From the Mixed-Up Files of Mrs. Basil E. Frankweiler", "E. L. Konigsburg", 1),
    ("The Westing Game", "Ellen Raskin", 1),
    ("Maniac Magee", "Jerry Spinelli", 1),
    ("Loser", "Jerry Spinelli", 1),
    ("Shiloh", "Phyllis Reynolds Naylor", 2),
    ("Because of Mr. Terupt", "Rob Buyea", 1),
    ("Wonderstruck", "Brian Selznick", 1),
    ("The Invention of Hugo Cabret", "Brian Selznick", 1),
]


def _isbn13_from_body(body12: str) -> str:
    if len(body12) != 12 or not body12.isdigit():
        raise ValueError(body12)
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body12))
    check = (10 - (total % 10)) % 10
    return body12 + str(check)


def _next_synthetic_isbn(used: set[str], serial: int) -> str:
    while True:
        body = f"9780309{serial:05d}"
        isbn = _isbn13_from_body(body)
        serial += 1
        if isbn not in used:
            used.add(isbn)
            return isbn


def build_rows(validator: IsbnValidator) -> tuple[list[list[object]], dict[str, int]]:
    """Return workbook rows and category counts."""
    rows: list[list[object]] = [
        [
            DEFAULT_WORKBOOK_COLUMN_ISBN,
            DEFAULT_WORKBOOK_COLUMN_TITLE,
            DEFAULT_WORKBOOK_COLUMN_AUTHOR,
            DEFAULT_WORKBOOK_COLUMN_COPIES,
        ]
    ]
    counts = {
        "valid": 0,
        "blank": 0,
        "invalid": 0,
        "duplicate": 0,
        "ambiguous": 0,
    }
    used_isbns: set[str] = set()

    for isbn, title, author, copies in _VERIFIED:
        assert validator.is_valid(isbn), f"invalid verified ISBN: {isbn} ({title})"
        assert isbn not in used_isbns, f"duplicate verified ISBN: {isbn}"
        used_isbns.add(isbn)
        rows.append([isbn, title, author, copies])
        counts["valid"] += 1

    serial = 1000
    for title, author, copies in _SYNTHETIC_TITLES:
        isbn = _next_synthetic_isbn(used_isbns, serial)
        serial += 1
        assert validator.is_valid(isbn)
        rows.append([isbn, title, author, copies])
        counts["valid"] += 1

    for title, author, copies in _BLANK_LOOKUP:
        rows.append(["", title, author, copies])
        counts["blank"] += 1

    for title, author, copies in _AMBIGUOUS:
        rows.append(["", title, author, copies])
        counts["ambiguous"] += 1

    invalid_specs = [
        ("1234567890123", "Broken ISBN Mystery", "Sample Author", 1),
        ("978006440055", "Too-Short ISBN Adventure", "Sample Author", 2),
        ("97800644005581", "Too-Long ISBN Adventure", "Sample Author", 1),
        ("978ABCDEFGHIJ", "Letters Instead of Digits", "Sample Author", 1),
        ("0000000000000", "All-Zero ISBN", "Sample Author", 2),
        ("9781234567890", "Bad Check Digit Book", "Sample Author", 1),
        ("ISBN-9780064400558", "Prefixed ISBN String", "Sample Author", 1),
        ("978-0-06-440055", "Incomplete Hyphenated ISBN", "Sample Author", 2),
        ("1111111111111", "Repeating Ones ISBN", "Sample Author", 1),
    ]
    for isbn, title, author, copies in invalid_specs:
        assert not validator.is_valid(isbn), f"expected invalid: {isbn}"
        rows.append([isbn, title, author, copies])
        counts["invalid"] += 1

    # Duplicate rows (same title/author as earlier valid entries) to exercise cache.
    duplicate_sources = [
        ("9780064400558", "Charlotte's Web", "E. B. White", 1),
        ("9780394800011", "The Cat in the Hat", "Dr. Seuss", 2),
        ("9780545581608", "Dog Man", "Dav Pilkey", 1),
        ("9780810993136", "Diary of a Wimpy Kid", "Jeff Kinney", 1),
        ("9780061906220", "Pete the Cat: I Love My White Shoes", "Eric Litwin", 1),
        ("", "Charlotte's Web", "E. B. White", 1),  # blank dup → cache after enrich
        ("", "The Cat in the Hat", "Dr. Seuss", 1),
        ("9780679824114", "Dinosaurs Before Dark", "Mary Pope Osborne", 1),
        ("9781423133087", "We Are in a Book!", "Mo Willems", 1),
    ]
    for isbn, title, author, copies in duplicate_sources:
        rows.append([isbn, title, author, copies])
        counts["duplicate"] += 1

    return rows, counts


def write_workbook(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = DEFAULT_WORKBOOK_SHEET_NAME
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


def main() -> None:
    validator = IsbnValidator()
    rows, counts = build_rows(validator)
    book_rows = len(rows) - 1
    total_labels = sum(int(row[3]) for row in rows[1:])
    pages = (total_labels + 29) // 30
    write_workbook(OUTPUT, rows)
    print(f"Wrote {OUTPUT}")
    print(f"Books: {book_rows}")
    print(f"Category counts: {counts}")
    print(f"Total label copies: {total_labels}")
    print(f"Avery 5160 pages (30/page): {pages}")


if __name__ == "__main__":
    main()
