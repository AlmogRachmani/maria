import os

def extract_mp4_files(input_file, output_dir):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    with open(input_file, "rb") as f:
        data = f.read()

    offset = 0
    file_count = 0
    total_data_length = len(data)

    while offset < total_data_length:
        # Check if there's enough data for an MP4 header
        if offset + 8 > total_data_length:
            print("No more valid MP4 headers found.")
            break

        # Read the atom size (4 bytes) and type (4 bytes)
        atom_size = int.from_bytes(data[offset:offset + 4], "big")
        atom_type = data[offset + 4:offset + 8].decode("utf-8", errors="ignore")

        # Validate the atom size
        if atom_size < 8 or offset + atom_size > total_data_length:
            print(f"Invalid or incomplete atom at offset {offset}.")
            break

        # Check if the atom type indicates an MP4 file (start with ftyp)
        if atom_type == "ftyp":
            file_count += 1
            print(f"MP4 file detected at offset {offset} with size {atom_size} bytes.")

            # Set the starting point of the next file to the end of this one
            next_file_offset = offset + atom_size
            while next_file_offset < total_data_length:
                # Find the next 'ftyp' atom (start of the next file)
                next_atom_size = int.from_bytes(data[next_file_offset:next_file_offset + 4], "big")
                next_atom_type = data[next_file_offset + 4:next_file_offset + 8].decode("utf-8", errors="ignore")

                if next_atom_type == "ftyp":
                    break  # Found the next MP4 file, stop here
                
                # Continue searching until next 'ftyp' is found
                next_file_offset += next_atom_size
            
            # Extract the current MP4 content
            output_file = os.path.join(output_dir, f"output_{file_count}.mp4")
            with open(output_file, "wb") as out_f:
                print(f"Creating new MP4 file: {output_file}")
                out_f.write(data[offset:next_file_offset])

        # Move to the next atom (or the next hidden MP4 segment)
        offset = next_file_offset

    print(f"Extraction complete. Total MP4 files extracted: {file_count}")


# Example usage
input_file_path = "decode_.mp4"  # Replace with your file path
output_directory = "extracted_files"
extract_mp4_files(input_file_path, output_directory)
