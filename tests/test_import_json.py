import unittest

from sqlalchemy.dialects import postgresql

from scripts.import_json import normalize_item, upsert_items


class RecordingConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)


class ImportJsonTests(unittest.TestCase):
    def test_v2_classification_survives_normalization(self):
        item = normalize_item({
            "id": "example:1",
            "title": "교육 프로그램",
            "category": {"code": "education", "name": "교육·강좌"},
            "taxonomy_version": "2.0",
            "subcategories": [{"code": "IT", "name": "IT"}],
        })
        self.assertEqual(item["category"], "EDUCATION")
        self.assertEqual(item["category_name"], "교육·강좌")
        self.assertEqual(item["taxonomy_version"], "2.0")
        self.assertEqual(item["subcategories"], [{"code": "IT", "name": "IT"}])

    def test_legacy_category_remains_supported(self):
        item = normalize_item({
            "id": "example:1", "title": "교육 프로그램", "category": "education",
        })
        self.assertEqual(item["category"], "EDUCATION")
        self.assertIsNone(item["category_name"])
        self.assertEqual(item["subcategories"], [])

    def test_reimport_updates_classification_of_existing_id(self):
        connection = RecordingConnection()
        result = upsert_items(connection, [{
            "id": "example:1",
            "title": "교육 프로그램",
            "category": {"code": "EDUCATION", "name": "교육·강좌"},
            "taxonomy_version": "2.0",
            "subcategories": [{"code": "IT", "name": "IT"}],
        }])
        self.assertEqual(result, (1, 0))
        sql = str(connection.statements[0].compile(dialect=postgresql.dialect()))
        update_clause = sql.split("DO UPDATE SET", 1)[1]
        for column in ("category_name", "taxonomy_version", "subcategories"):
            with self.subTest(column=column):
                self.assertIn(f"{column} = excluded.{column}", update_clause)


if __name__ == "__main__":
    unittest.main()
