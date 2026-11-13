import os
import tempfile
import unittest

from experiments.make_diagram import main


class TestDiagram(unittest.TestCase):
    def test_diagram_is_generated_from_the_model(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "fig.png")
            main(["--out", out])
            self.assertTrue(os.path.getsize(out) > 10_000)


if __name__ == "__main__":
    unittest.main()