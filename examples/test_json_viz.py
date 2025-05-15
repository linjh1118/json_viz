import sys
from pathlib import Path as p
sys.path.append(str(p(__file__).parent.parent))

from src.json_viz.core import JsonVisualizer

# Test with enhanced version
input_file="assets/data.jsonl"
output_file="assets/data.html"
JsonVisualizer.visualize(
    input_file=input_file,
    output_file=output_file,
    textual_cols=["question", "answer", "results"],
    # Don't drop metadata to test dictionary handling
    title=f"Visualization of {input_file}"
)

print("Test completed successfully. Check the output HTML file in the assets directory.")