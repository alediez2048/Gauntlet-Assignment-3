# Fortran Source Format Reference

## Fixed-Form vs Free-Form Detection

Detect the format before parsing. Heuristics:

| Signal | Fixed-Form | Free-Form |
|--------|-----------|-----------|
| File extension | `.f`, `.f77` | `.f90`, `.f95` |
| Col 1 comment | `C`, `c`, `*` in column 1 | Not used |
| Col 6 continuation | Non-blank character in col 6 | `&` at end of line |
| Inline comment | Not standard | `!` anywhere on line |
| Line length | Max 72 characters | Max 132 characters |

If heuristics conflict, prefer extension-based detection. Allow per-codebase override in config.

## Fixed-Form Layout

```
Col  1:     Comment indicator (C, c, * → comment line)
Cols 1-5:   Label/statement number field
Col  6:     Continuation column (non-blank = continuation of previous line)
Cols 7-72:  Statement field (actual code)
Cols 73+:   Ignored (identification field)
```

## Free-Form Rules

- Lines up to 132 characters
- `!` starts an inline comment (rest of line is comment)
- `&` at end of line = continuation on next line
- No column restrictions

## Preprocessing Steps

1. Detect fixed vs free form
2. For fixed-form:
   - Extract col 1 comments (`C`, `c`, `*`)
   - Strip cols 73+ (identification)
   - Handle col 6 continuations
   - Extract cols 7-72 as code
3. For free-form:
   - Extract `!` inline comments
   - Handle `&` continuations
   - Full line is code (minus comments)

## Subroutine/Function Detection (for Chunker)

Boundary markers:

```fortran
PROGRAM program-name         ! start of main program
SUBROUTINE sub-name(args)    ! start of subroutine
FUNCTION func-name(args)     ! start of function
MODULE module-name           ! start of module
END                          ! end of current unit
END SUBROUTINE sub-name      ! explicit end
END FUNCTION func-name       ! explicit end
END PROGRAM program-name     ! explicit end
END MODULE module-name       ! explicit end
```

Detection rules:
- Case-insensitive matching
- `name` = the identifier after the keyword
- A unit ends at its corresponding `END` statement or at the start of the next unit
- Set `chunk_type` to `"subroutine"`, `"function"`, `"program"`, or `"module"`

## Dependency Extraction

Look for these patterns:
- `CALL sub-name(args)` — subroutine call
- `USE module-name` — module dependency
- `INCLUDE 'filename'` — file inclusion
- Function references appear as identifiers in expressions (harder to detect — best-effort)

## Comment Patterns

Fixed-form:
```fortran
C     This is a comment (C in column 1)
c     Also a comment (lowercase c)
*     Also a comment (asterisk)
```

Free-form:
```fortran
x = 1.0  ! This is an inline comment
! This is a full-line comment
```
