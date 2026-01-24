
from backend.description_generator import generate_description
import sys

# Mock data
title = "【ReGLOSS】歌枠【火威青】"
desc = "火威青です。"
expected_found = False

# Run generation
output = generate_description("http://example.com", title, desc)

print("--- Generated Description ---")
print(output)
print("---------------------------")

if "#ReGLOSS" in output and "#ホロライブReGLOSS" not in output:
    print("SUCCESS: #ReGLOSS tag found correctly.")
else:
    print("FAILURE: Tag format incorrect for ReGLOSS.")

# Test FLOWGLOW
title2 = "【FLOWGLOW】歌枠【響咲リオナ】"
desc2 = "響咲リオナです。"
output2 = generate_description("http://example.com", title2, desc2)

if "#FLOWGLOW" in output2 and "#ホロライブFLOWGLOW" not in output2:
    print("SUCCESS: #FLOWGLOW tag found correctly.")
else:
    print("FAILURE: Tag format incorrect for FLOWGLOW.")
