from datasets import load_dataset

# Load the dataset in streaming mode
dataset = load_dataset("GBaker/MedQA-USMLE-4-options", split="train", streaming=True)

line_count = 100
extracted_data = []

for entry in dataset:
    # 1. Clean the question text (strip internal newlines)
    question = entry['question'].replace('\n', ' ').strip()
    
    # 2. Format options into a single unified block (using commas/spaces instead of pipes)
    opts = entry['options']
    options_block = f"A: {opts['A'].strip()}, B: {opts['B'].strip()}, C: {opts['C'].strip()}, D: {opts['D'].strip()}"
    
    # 3. Get the correct answer indicator
    answer_letter = entry['answer_idx']
    answer_text = opts.get(answer_letter, "").strip()
    answer_full = f"{answer_letter} ({answer_text})"
    
    # 4. Join the 3 pillars using a single pipe separator
    full_line = f"{question} | {options_block} | {answer_full}"
    extracted_data.append(full_line)
    
    if len(extracted_data) == line_count:
        break

# Save to file
output_file = "medqa_three_pillars_100.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for line in extracted_data:
        f.write(line + "\n")

print(f"Successfully saved 100 lines to '{output_file}'.")
