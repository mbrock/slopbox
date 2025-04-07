-- Better approach using SQLite's foreign key support along with PRAGMA statements
-- Begin transaction
BEGIN TRANSACTION;

-- Temporarily disable foreign key constraints
PRAGMA foreign_keys = OFF;

-- Create temporary table to hold existing data
CREATE TABLE temp_image_specs AS SELECT * FROM image_specs;

-- Drop the original table
DROP TABLE image_specs;

-- Recreate the table with the correct structure and constraints
CREATE TABLE image_specs (
    id INTEGER PRIMARY KEY,
    prompt TEXT NOT NULL,
    model TEXT NOT NULL,
    aspect_ratio TEXT NOT NULL,
    style TEXT DEFAULT 'realistic_image/natural_light',
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt, model, aspect_ratio, style)
);

-- Copy data back from the temporary table
INSERT INTO image_specs (id, prompt, model, aspect_ratio, style, created)
SELECT id, prompt, model, aspect_ratio, 
       COALESCE(style, 'realistic_image/natural_light') AS style, 
       created
FROM temp_image_specs;

-- Drop the temporary table
DROP TABLE temp_image_specs;

-- Re-enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Commit changes
COMMIT;

-- Verify the constraint is properly in place
PRAGMA table_info(image_specs);
PRAGMA index_list(image_specs);