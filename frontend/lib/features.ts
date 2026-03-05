export interface FeatureConfig {
  value: string;
  label: string;
  description: string;
  placeholder: string;
  examples: string[];
}

/**
 * Per-codebase example queries, keyed by codebase name then feature value.
 * Falls back to the feature's default examples when no codebase is selected
 * or when no codebase-specific examples exist for that feature.
 */
export const CODEBASE_EXAMPLES: Record<string, Record<string, string[]>> = {
  gnucobol: {
    code_explanation: [
      "What does the PROCEDURE DIVISION do?",
      "Explain the INIT-DATA paragraph",
      "How does the PERFORM statement work?",
    ],
    dependency_mapping: [
      "What paragraphs does MAIN-LOGIC call?",
      "Trace PERFORM calls in the main program",
      "What are the paragraph dependencies?",
    ],
    pattern_detection: [
      "What code patterns repeat across programs?",
      "Find patterns similar to error handling",
      "Find similar code to CALCULATE-INTEREST",
    ],
    impact_analysis: [
      "What breaks if INIT-DATA is modified?",
      "Impact of changing the FILE SECTION",
      "What depends on the PROCEDURE DIVISION?",
    ],
    documentation_gen: [
      "Generate docs for the PROCEDURE DIVISION",
      "Document the FILE SECTION",
      "Write docs for the main program",
    ],
    translation_hints: [
      "How would the file I/O look in Python?",
      "Translate PERFORM loops to Python",
      "What's the modern equivalent of this COBOL?",
    ],
    bug_pattern_search: [
      "Find potential bugs in the COBOL code",
      "Are there error handling issues?",
      "Check for common COBOL anti-patterns",
    ],
    business_logic: [
      "What business rules are implemented?",
      "Extract business logic from PROCEDURE DIVISION",
      "What calculations does this program perform?",
    ],
  },
  "opencobol-contrib": {
    code_explanation: [
      "What COBOL sample programs are available?",
      "How does file I/O work in these programs?",
      "Explain the WORKING-STORAGE SECTION",
    ],
    dependency_mapping: [
      "What paragraphs are called from the main flow?",
      "Trace PERFORM calls in the sample programs",
      "What CALL statements are used?",
    ],
    pattern_detection: [
      "What code patterns repeat across samples?",
      "Find patterns similar to file handling",
      "What validation patterns are used?",
    ],
    impact_analysis: [
      "What breaks if the file handling changes?",
      "Impact of modifying the data definitions",
      "What depends on the validation routines?",
    ],
    documentation_gen: [
      "Generate docs for the sample programs",
      "Document the file handling routines",
      "Write docs for the validation logic",
    ],
    translation_hints: [
      "How would the file I/O look in Python?",
      "Translate the validation logic to Python",
      "What's the Python equivalent of COBOL INSPECT?",
    ],
    bug_pattern_search: [
      "Find potential bugs in the COBOL samples",
      "Are there error handling gaps?",
      "Check for common anti-patterns",
    ],
    business_logic: [
      "What business rules are in the validation logic?",
      "Extract business logic from the samples",
      "What calculations do these programs perform?",
    ],
  },
  lapack: {
    code_explanation: [
      "How does DGETRF perform LU factorization?",
      "How does DGESV solve linear systems?",
      "How does DGETRS solve triangular systems?",
    ],
    dependency_mapping: [
      "What subroutines does DGESV call?",
      "What are the dependencies of DGETRF?",
      "Trace calls from DGESVD",
    ],
    pattern_detection: [
      "What patterns appear in LAPACK driver routines?",
      "Find similar code to DGETRF",
      "What error handling patterns are used?",
    ],
    impact_analysis: [
      "What breaks if DGETRF is modified?",
      "Impact of changing XERBLA error handling",
      "What depends on DGETRS?",
    ],
    documentation_gen: [
      "Generate docs for DGESV",
      "Document the DGETRF subroutine",
      "Write docs for the error handling routines",
    ],
    translation_hints: [
      "How would DGETRF look in Python with NumPy?",
      "Translate DGESV to Python",
      "What's the SciPy equivalent of DGESVD?",
    ],
    bug_pattern_search: [
      "Find potential issues in error handling",
      "Are there any workspace sizing bugs?",
      "Check for common Fortran anti-patterns",
    ],
    business_logic: [
      "What numerical algorithms are implemented?",
      "What matrix operations does LAPACK provide?",
      "What solvers are available for linear systems?",
    ],
  },
  blas: {
    code_explanation: [
      "What does DGEMM do for matrix multiplication?",
      "What does DAXPY compute?",
      "What does DCOPY do?",
    ],
    dependency_mapping: [
      "What BLAS routines are used internally?",
      "What does DGEMM depend on?",
      "What routines call DSCAL?",
    ],
    pattern_detection: [
      "What patterns appear across BLAS routines?",
      "Find code similar to DAXPY",
      "What loop patterns are common in BLAS?",
    ],
    impact_analysis: [
      "What would break if DGEMM were modified?",
      "Impact of changing DAXPY",
      "What depends on DSCAL?",
    ],
    documentation_gen: [
      "Generate docs for DGEMM",
      "Document the DAXPY routine",
      "Write docs for DCOPY",
    ],
    translation_hints: [
      "How would DAXPY look in Python with NumPy?",
      "Translate DGEMM to Python",
      "What's the NumPy equivalent of DSCAL?",
    ],
    bug_pattern_search: [
      "Find potential issues in BLAS routines",
      "Are there parameter validation gaps?",
      "Check for numerical stability issues",
    ],
    business_logic: [
      "What vector operations does BLAS provide?",
      "What matrix operations are available?",
      "What does DSCAL compute?",
    ],
  },
  gfortran: {
    code_explanation: [
      "How are Fortran array intrinsics tested?",
      "How does Fortran handle array operations?",
      "What Fortran intrinsic functions are tested?",
    ],
    dependency_mapping: [
      "What modules are used in the test cases?",
      "What subroutine calls appear in tests?",
      "How do test programs depend on each other?",
    ],
    pattern_detection: [
      "What testing patterns are used?",
      "Find common patterns in gfortran tests",
      "What assertion patterns are used?",
    ],
    impact_analysis: [
      "What tests would break if array handling changes?",
      "Impact of modifying intrinsic functions",
      "What depends on the I/O test suite?",
    ],
    documentation_gen: [
      "Generate docs for the array test suite",
      "Document the intrinsic function tests",
      "Write docs for the I/O test cases",
    ],
    translation_hints: [
      "How would these Fortran tests look in Python?",
      "Translate the array operations to NumPy",
      "What's the modern equivalent of these intrinsics?",
    ],
    bug_pattern_search: [
      "Find potential issues in the test cases",
      "Are there common Fortran pitfalls tested?",
      "What edge cases are covered?",
    ],
    business_logic: [
      "What Fortran features are being validated?",
      "What compiler behaviors are tested?",
      "What numerical operations are covered?",
    ],
  },
};

export const FEATURES: FeatureConfig[] = [
  {
    value: "code_explanation",
    label: "Code Explanation",
    description: "Explain what code does in plain English",
    placeholder: "e.g., What does the PROCEDURE DIVISION do?",
    examples: [
      "What does the PROCEDURE DIVISION do?",
      "Explain the INIT-DATA paragraph",
      "What does CALCULATE-INTEREST do?",
    ],
  },
  {
    value: "dependency_mapping",
    label: "Dependency Mapping",
    description: "Trace PERFORM/CALL chains between paragraphs",
    placeholder: "e.g., What paragraphs does MAIN-LOGIC call?",
    examples: [
      "What paragraphs does MAIN-LOGIC call?",
      "Trace PERFORM calls from PROCESS-RECORDS",
      "What are the dependencies of the INIT section?",
    ],
  },
  {
    value: "pattern_detection",
    label: "Pattern Detection",
    description: "Find structurally similar code across the codebase",
    placeholder: "e.g., Find patterns similar to error handling",
    examples: [
      "Find patterns similar to error handling routines",
      "What code patterns repeat across the codebase?",
      "Find similar code to CALCULATE-INTEREST",
    ],
  },
  {
    value: "impact_analysis",
    label: "Impact Analysis",
    description: "What breaks if this code changes?",
    placeholder: "e.g., What breaks if INIT-DATA changes?",
    examples: [
      "What would break if INIT-DATA is modified?",
      "What depends on CALCULATE-INTEREST?",
      "Impact of changing the FILE SECTION",
    ],
  },
  {
    value: "documentation_gen",
    label: "Documentation",
    description: "Auto-generate docs for undocumented code",
    placeholder: "e.g., Generate docs for the FILE SECTION",
    examples: [
      "Generate documentation for the FILE SECTION",
      "Document the MAIN-LOGIC paragraph",
      "Write docs for PROCESS-RECORDS",
    ],
  },
  {
    value: "translation_hints",
    label: "Translation Hints",
    description: "Modern language equivalents (Python)",
    placeholder: "e.g., How would PROCESS-RECORDS look in Python?",
    examples: [
      "How would PROCESS-RECORDS look in Python?",
      "Translate CALCULATE-INTEREST to Python",
      "What's the modern equivalent of this COBOL pattern?",
    ],
  },
  {
    value: "bug_pattern_search",
    label: "Bug Patterns",
    description: "Detect anti-patterns and potential bugs",
    placeholder: "e.g., Find potential bug patterns",
    examples: [
      "Find potential bug patterns in this codebase",
      "Are there any common anti-patterns?",
      "Check for error handling issues",
    ],
  },
  {
    value: "business_logic",
    label: "Business Logic",
    description: "Extract business rules in plain English",
    placeholder: "e.g., What business rules are in CALCULATE-INTEREST?",
    examples: [
      "What business rules are in CALCULATE-INTEREST?",
      "Extract business logic from the PROCEDURE DIVISION",
      "What calculations does this program perform?",
    ],
  },
];
