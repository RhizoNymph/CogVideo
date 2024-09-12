import os
import sys
import instructor
from pydantic import BaseModel
from anthropic import Anthropic
from openai import OpenAI
import csv
import argparse
import logging
import io

logging.basicConfig(level=logging.INFO)

class PromptBatch(BaseModel):
    preamble: str
    csv: str

def parse_csv(csv_string):
    # Use StringIO to create a file-like object from the string
    csv_file = io.StringIO(csv_string)
    # Use csv.reader with strict quoting to handle commas within fields
    reader = csv.reader(csv_file, strict=True, quoting=csv.QUOTE_ALL)
    return list(reader)

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("num_prompts", type=int, help="Number of prompts to generate")
    parser.add_argument("theme", help="Theme for the prompts")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic", help="API provider (default: anthropic)")
    args = parser.parse_args()

    logging.info(f"Theme: {args.theme}")
    logging.info(f"Provider: {args.provider}")

    # Create client based on provider
    logging.info("Creating client")
    if args.provider == "anthropic":
        client = instructor.from_anthropic(Anthropic())
        model = "claude-3-opus-20240229"
    else:
        client = instructor.from_openai(OpenAI())
        model = "gpt-4"

    # Generate prompts
    logging.info("Sending message to generate prompts")
    try:
        message = client.chat.completions.create(
            model=model,
            response_model=PromptBatch,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"""Generate a CSV with exactly {args.num_prompts} rows of content (no header row needed). The format should be:

"Detailed prompt 1",output1.mp4
"Detailed prompt 2",output2.mp4
...

Each prompt should be for a video generation model based on the theme '{args.theme}'. Be creative and diverse in the prompts. Ensure there are exactly {args.num_prompts} rows. Make sure to enclose each prompt in double quotes to handle any commas within the prompt text."""
                }
            ]
        )
    except Exception as e:
        logging.error(f"Failed to reach the model: {str(e)}")
        sys.exit(1)

    # Parse and validate CSV
    logging.info("Parsing and validating generated CSV")
    try:
        csv_content = parse_csv(message.csv.strip())

        if len(csv_content) < 1:  # Check if we have at least one row
            raise ValueError(f"AI did not generate any valid CSV rows. Received: {message.csv}")

        # Check if the first row looks like a header row
        if csv_content[0] == ['prompt', 'output_path']:
            headers = csv_content[0]
            prompts = csv_content[1:]
        else:
            # If no header, add it and treat all rows as prompts
            headers = ['prompt', 'output_path']
            prompts = csv_content

        if len(prompts) != args.num_prompts:
            raise ValueError(f"Incorrect number of prompts generated. Expected {args.num_prompts}, got {len(prompts)}")

        for i, row in enumerate(prompts, 1):
            if len(row) != 2:
                raise ValueError(f"Invalid row {i}: {row}. Expected 2 columns, got {len(row)}")
            if not row[1].endswith('.mp4'):
                raise ValueError(f"Invalid output path in row {i}: {row[1]}. Must end with .mp4")
    except Exception as e:
        logging.error(f"Error in AI-generated CSV: {str(e)}")
        logging.error(f"Generated content: {message.csv}")
        sys.exit(1)

    # Create batch directory
    logging.info("Creating batch directory")
    batches = os.listdir("./batches")
    batches = [i.replace("batch", "") for i in batches]
    batches = [int(i.split("-")[0]) for i in batches if i.split("-")[0].isdigit()]
    max_n = max(batches) if batches else 0
    current_n = max_n + 1
    sanitized_theme = args.theme.replace(" ", "_")
    out_dir = f"./batches/batch{current_n}-{sanitized_theme}"
    os.makedirs(out_dir, exist_ok=True)

    # Write validated CSV
    logging.info("Writing prompts to CSV")
    csv_path = os.path.join(out_dir, "prompts.csv")
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        for prompt, output_path in prompts:
            updated_output_path = os.path.join(out_dir, output_path)
            writer.writerow([prompt, updated_output_path])

    logging.info("CSV file created successfully")

    # Run the generation script
    logging.info("Running generation script")
    logging.info(f"CSV path: {csv_path}")
    os.system(f"python3 cli_demo.py --prompts {csv_path}")

if __name__ == "__main__":
    main()
