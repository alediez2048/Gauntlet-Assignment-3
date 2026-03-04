export interface FeatureConfig {
  value: string;
  label: string;
  description: string;
  placeholder: string;
  examples: string[];
}

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
