# COBOL Source Format Reference

## Column Layout (Fixed Format)

```
Cols 1-6:   Sequence number area (STRIP — not code)
Col  7:     Indicator area
              ' ' = normal line
              '*' = comment line (extract to comments list)
              '/' = comment + page break
              '-' = continuation of previous line
              'D' = debugging line (treat as comment)
Cols 8-11:  Area A (division/section/paragraph headers start here)
Cols 12-72: Area B (statements and clauses)
Cols 73-80: Identification area (STRIP — not code)
```

## Preprocessing Steps

1. Read file with `chardet` encoding detection
2. For each line:
   - Strip cols 1-6 (sequence numbers)
   - Strip cols 73-80 (identification area)
   - Check col 7 for indicator:
     - `*`, `/`, `D` → extract as comment, skip from code
     - `-` → append to previous line (continuation)
     - ` ` → normal code line
3. Preserve cols 8-72 as the actual code
4. Normalize whitespace but preserve logical structure

## Paragraph Detection (for Chunker)

COBOL paragraphs are named blocks in the PROCEDURE DIVISION:

```cobol
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           PERFORM INIT-DATA.
           PERFORM PROCESS-RECORDS.
           STOP RUN.
       INIT-DATA.
           MOVE ZEROS TO WS-COUNTER.
       PROCESS-RECORDS.
           READ INPUT-FILE.
```

Detection rules:
- A paragraph name starts in Area A (cols 8-11)
- Ends with a period on the same line
- A paragraph ends where the next paragraph begins or at the end of the division
- `PROCEDURE DIVISION.` itself is not a paragraph

## Division Structure

COBOL programs have up to 4 divisions (in order):

1. `IDENTIFICATION DIVISION` — program name, metadata
2. `ENVIRONMENT DIVISION` — file assignments, configuration
3. `DATA DIVISION` — variable declarations (WORKING-STORAGE, FILE SECTION)
4. `PROCEDURE DIVISION` — executable code (paragraphs and sections)

Set `division` metadata based on which division the chunk falls within.

## Dependency Extraction

Look for these patterns to populate `dependencies`:
- `PERFORM paragraph-name`
- `PERFORM paragraph-name THRU paragraph-name`
- `CALL "program-name"`
- `COPY copybook-name`

## COPY Statements

`COPY member-name.` includes external source. Files with `.cpy` extension are copybooks. Track as dependencies but do not recurse into them during chunking (they'll be chunked separately).

## Comment Patterns

```cobol
000100*THIS IS A FULL-LINE COMMENT
000200/THIS IS A PAGE-BREAK COMMENT
000300DTHIS IS A DEBUG LINE
```

All have the indicator in column 7.
