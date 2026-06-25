export interface ToolInfo {
  displayName: string;
  description: string;
  docUrl: string;
  category: 'security' | 'correctness' | 'design' | 'hygiene' | 'consistency';
  rulePrefix: string;
  ruleUrlTemplate: string | null;
  sampleRules: string[];
}

export const TOOL_INFO: Record<string, ToolInfo> = {
  'bandit': {
    displayName: 'Bandit',
    description: 'Python security vulnerability scanner. Finds common security issues in Python code including injection, hardcoded passwords, and insecure configurations.',
    docUrl: 'https://bandit.readthedocs.io/en/latest/',
    category: 'security',
    rulePrefix: 'B',
    ruleUrlTemplate: 'https://bandit.readthedocs.io/en/latest/plugins/b{id}_hardcoded_tmp_directory.html',
    sampleRules: ['B101 assert_used', 'B108 hardcoded_tmp_directory', 'B301 pickle', 'B501 request_with_no_cert_validation', 'B602 subprocess_popen_with_shell_equals_true'],
  },
  'ruff': {
    displayName: 'Ruff',
    description: 'Fast Python linter covering pyflakes, pycodestyle, isort, and more. Checks code style, imports, and common errors.',
    docUrl: 'https://docs.astral.sh/ruff/rules/',
    category: 'correctness',
    rulePrefix: 'E/F/W/S/I/N/D',
    ruleUrlTemplate: 'https://docs.astral.sh/ruff/rules/#{id}',
    sampleRules: ['E501 line-too-long', 'F401 unused-import', 'F841 unused-variable', 'W291 trailing-whitespace', 'I001 unsorted-imports'],
  },
  'mypy': {
    displayName: 'Mypy',
    description: 'Static type checker for Python. Verifies type annotations and catches type-related errors before runtime.',
    docUrl: 'https://mypy.readthedocs.io/en/stable/error_code_list.html',
    category: 'correctness',
    rulePrefix: 'mypy',
    ruleUrlTemplate: 'https://mypy.readthedocs.io/en/stable/error_code_list.html',
    sampleRules: ['mypy-error type assignment', 'mypy-error missing return', 'mypy-error incompatible types'],
  },
  'semgrep': {
    displayName: 'Semgrep',
    description: 'Multi-language pattern-based static analysis. Uses rules to find security vulnerabilities, bugs, and anti-patterns across many languages.',
    docUrl: 'https://semgrep.dev/docs/',
    category: 'security',
    rulePrefix: '',
    ruleUrlTemplate: 'https://semgrep.dev/r/{id}',
    sampleRules: ['python.lang.security.audit.eval-detected', 'python.lang.security.deserialization.avoid-pickle', 'javascript.express.security.audit.xss.no-direct-response-write'],
  },
  'shellcheck': {
    displayName: 'ShellCheck',
    description: 'Shell script static analysis tool. Finds bugs, syntax issues, and security problems in bash/sh scripts.',
    docUrl: 'https://www.shellcheck.net/',
    category: 'correctness',
    rulePrefix: 'SC',
    ruleUrlTemplate: 'https://www.shellcheck.net/wiki/{id}',
    sampleRules: ['SC2086 double-quote-variables', 'SC2046 quote-command-substitution', 'SC1091 not-following-source', 'SC2034 unused-variable'],
  },
  'gitleaks': {
    displayName: 'Gitleaks',
    description: 'Detects hardcoded secrets, API keys, passwords, and tokens in git repositories.',
    docUrl: 'https://github.com/gitleaks/gitleaks',
    category: 'security',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['generic-api-key', 'aws-access-key', 'github-token', 'private-key', 'jwt'],
  },
  'repo-scanner': {
    displayName: 'Repo Scanner (Trivy + Built-in)',
    description: 'Repository-level scanner using Trivy for vulnerabilities, secrets, and misconfigurations, plus built-in checks for committed packages, sensitive files, and large files.',
    docUrl: 'https://trivy.dev/docs/',
    category: 'security',
    rulePrefix: 'CVE/AVD/GHSA',
    ruleUrlTemplate: null,
    sampleRules: ['CVE-2023-xxxx vulnerability', 'AVD-DS-0001 misconfiguration', 'Committed .venv/', 'Sensitive file .env'],
  },
  'checkov': {
    displayName: 'Checkov',
    description: 'Infrastructure-as-code scanner for Dockerfiles, Terraform, Kubernetes, and CloudFormation. Checks against CIS benchmarks.',
    docUrl: 'https://www.checkov.io/5.Policy%20Index/all.html',
    category: 'security',
    rulePrefix: 'CKV',
    ruleUrlTemplate: 'https://docs.prismacloud.io/en/enterprise-edition/policy-reference',
    sampleRules: ['CKV_DOCKER_2 healthcheck', 'CKV_DOCKER_3 user', 'CKV_AWS_18 s3-logging', 'CKV_K8S_1 pod-security'],
  },
  'osv-scanner': {
    displayName: 'OSV Scanner',
    description: 'Scans dependencies against the Open Source Vulnerabilities database. Checks requirements.txt, package.json, go.sum, and Cargo.lock.',
    docUrl: 'https://osv.dev/',
    category: 'security',
    rulePrefix: 'GHSA/PYSEC/CVE',
    ruleUrlTemplate: 'https://osv.dev/vulnerability/{id}',
    sampleRules: ['GHSA-xxxx-xxxx-xxxx', 'PYSEC-2023-xxx', 'CVE-2023-xxxx'],
  },
  'pip-audit': {
    displayName: 'pip-audit',
    description: 'Audits Python packages for known vulnerabilities using the PyPI advisory database.',
    docUrl: 'https://github.com/pypa/pip-audit',
    category: 'security',
    rulePrefix: 'PYSEC/CVE',
    ruleUrlTemplate: 'https://osv.dev/vulnerability/{id}',
    sampleRules: ['PYSEC-2023-xxx', 'CVE-2023-xxxx'],
  },
  'hadolint': {
    displayName: 'Hadolint',
    description: 'Dockerfile linter that checks for best practices and common mistakes in Dockerfiles.',
    docUrl: 'https://github.com/hadolint/hadolint#rules',
    category: 'correctness',
    rulePrefix: 'DL',
    ruleUrlTemplate: 'https://github.com/hadolint/hadolint/wiki/{id}',
    sampleRules: ['DL3008 pin-versions', 'DL3009 delete-apt-cache', 'DL4006 set-pipefail', 'DL3025 use-json-cmd'],
  },
  'radon': {
    displayName: 'Radon',
    description: 'Python code complexity analyzer. Measures cyclomatic complexity, maintainability index, and Halstead metrics.',
    docUrl: 'https://radon.readthedocs.io/',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['High complexity (rank C+)', 'Cyclomatic complexity > 10'],
  },
  'security-patterns': {
    displayName: 'Security Patterns',
    description: 'Built-in regex-based scanner for common security anti-patterns: eval(), exec(), subprocess shell=True, hardcoded secrets, unsafe YAML loading.',
    docUrl: '',
    category: 'security',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Use of eval()', 'subprocess with shell=True', 'Hardcoded secret pattern', 'pickle.load usage'],
  },
  'complexity': {
    displayName: 'Complexity Analyzer',
    description: 'Measures code complexity metrics including cyclomatic complexity, nesting depth, and function length.',
    docUrl: '',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Excessive complexity', 'Deep nesting', 'Long function'],
  },
  'dead-code': {
    displayName: 'Dead Code Detector',
    description: 'Finds unused functions, classes, variables, and imports using vulture or heuristic analysis.',
    docUrl: 'https://github.com/jendrikseipp/vulture',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Unused function', 'Unused import', 'Unused variable'],
  },
  'jscpd': {
    displayName: 'JSCPD',
    description: 'Copy-paste detector. Finds duplicate code blocks across files in multiple languages.',
    docUrl: 'https://github.com/kucherenko/jscpd',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Code duplication detected'],
  },
  'sqlfluff': {
    displayName: 'SQLFluff',
    description: 'SQL linter and formatter. Checks SQL style, formatting, and common anti-patterns.',
    docUrl: 'https://docs.sqlfluff.com/en/stable/rules.html',
    category: 'correctness',
    rulePrefix: 'L',
    ruleUrlTemplate: 'https://docs.sqlfluff.com/en/stable/rules.html#{id}',
    sampleRules: ['L001 trailing-whitespace', 'L003 indentation', 'L010 keyword-case'],
  },
  'markdownlint': {
    displayName: 'Markdownlint',
    description: 'Markdown style checker. Ensures consistent formatting in documentation files.',
    docUrl: 'https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md',
    category: 'correctness',
    rulePrefix: 'MD',
    ruleUrlTemplate: 'https://github.com/DavidAnson/markdownlint/blob/main/doc/{id}.md',
    sampleRules: ['MD001 heading-increment', 'MD013 line-length', 'MD041 first-line-heading'],
  },
  'prettier': {
    displayName: 'Prettier',
    description: 'Opinionated code formatter. Checks if files conform to Prettier formatting rules.',
    docUrl: 'https://prettier.io/docs/en/',
    category: 'consistency',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['File not formatted'],
  },
  'stylelint': {
    displayName: 'Stylelint',
    description: 'CSS linter. Checks for errors and enforces conventions in CSS, SCSS, and Less files.',
    docUrl: 'https://stylelint.io/user-guide/rules/',
    category: 'correctness',
    rulePrefix: '',
    ruleUrlTemplate: 'https://stylelint.io/user-guide/rules/{id}',
    sampleRules: ['color-no-invalid-hex', 'declaration-block-no-duplicate-properties'],
  },
  'pip-licenses': {
    displayName: 'pip-licenses',
    description: 'Checks Python package licenses for compliance. Flags copyleft and restrictive licenses.',
    docUrl: 'https://github.com/raimon49/pip-licenses',
    category: 'hygiene',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Copyleft license: GPL', 'Unknown license'],
  },
  'version-drift': {
    displayName: 'Version Drift',
    description: 'Detects unpinned or loosely pinned dependencies that may introduce breaking changes.',
    docUrl: '',
    category: 'security',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Unpinned dependency', 'Loose version constraint'],
  },
  'test-coverage-gap': {
    displayName: 'Test Coverage Gap',
    description: 'Identifies source files that lack corresponding test files.',
    docUrl: '',
    category: 'correctness',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['No test file found for module'],
  },
  'unused-module': {
    displayName: 'Unused Module',
    description: 'Detects Python modules that are not imported by any other module in the project.',
    docUrl: '',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Module not imported by any other module'],
  },
  'interface-checker': {
    displayName: 'Interface Checker',
    description: 'Checks for API interface consistency — missing docstrings, inconsistent parameter naming.',
    docUrl: '',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Missing docstring', 'Inconsistent naming'],
  },
  'migration-checker': {
    displayName: 'Migration Checker',
    description: 'Checks database migration files for safety — destructive operations, missing rollbacks.',
    docUrl: '',
    category: 'correctness',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Destructive migration', 'Missing rollback'],
  },
  'call-graph': {
    displayName: 'Call Graph Analyzer',
    description: 'Analyzes function call relationships to detect circular dependencies and unreachable code.',
    docUrl: '',
    category: 'design',
    rulePrefix: '',
    ruleUrlTemplate: null,
    sampleRules: ['Circular dependency', 'Unreachable function'],
  },
  'hygiene-checker': {
    displayName: 'Hygiene Checker',
    description: 'Built-in file classifier. Detects sensitive files (.env), flags binary files, and excludes package directories from scanning.',
    docUrl: '',
    category: 'hygiene',
    rulePrefix: 'HYG',
    ruleUrlTemplate: null,
    sampleRules: ['HYG-0001 Sensitive file in repository'],
  },
};

export function parseRuleId(title: string): string | null {
  const match = title.match(/^\[([^\]]+)\]/);
  return match ? match[1] : null;
}

export function getRuleUrl(source: string, ruleId: string): string | null {
  if (ruleId.startsWith('CVE-')) return `https://nvd.nist.gov/vuln/detail/${ruleId}`;
  if (ruleId.startsWith('GHSA-')) return `https://osv.dev/vulnerability/${ruleId}`;
  if (ruleId.startsWith('PYSEC-')) return `https://osv.dev/vulnerability/${ruleId}`;
  if (ruleId.startsWith('AVD-')) return `https://avd.aquasec.com/misconfig/${ruleId.toLowerCase()}`;
  if (ruleId.startsWith('CKV_')) return 'https://www.checkov.io/5.Policy%20Index/all.html';

  const tool = TOOL_INFO[source];
  if (!tool?.ruleUrlTemplate) return tool?.docUrl || null;

  return tool.ruleUrlTemplate.replace('{id}', ruleId);
}

export function getCweUrl(cwe: string): string {
  const num = cwe.replace(/^CWE-/i, '').replace(/\D/g, '');
  return `https://cwe.mitre.org/data/definitions/${num}.html`;
}

export function getToolDocUrl(source: string): string {
  return TOOL_INFO[source]?.docUrl || '';
}

export const COMMON_CWES: Array<{ id: string; name: string; description: string }> = [
  { id: 'CWE-79', name: 'Cross-site Scripting (XSS)', description: 'Improper neutralization of input during web page generation.' },
  { id: 'CWE-89', name: 'SQL Injection', description: 'Improper neutralization of special elements used in an SQL command.' },
  { id: 'CWE-78', name: 'OS Command Injection', description: 'Improper neutralization of special elements used in an OS command.' },
  { id: 'CWE-22', name: 'Path Traversal', description: 'Improper limitation of a pathname to a restricted directory.' },
  { id: 'CWE-352', name: 'Cross-Site Request Forgery (CSRF)', description: 'The web application does not verify that a request was intentionally provided by the user.' },
  { id: 'CWE-434', name: 'Unrestricted Upload', description: 'The software allows upload of dangerous file types.' },
  { id: 'CWE-502', name: 'Deserialization of Untrusted Data', description: 'The application deserializes untrusted data without verification.' },
  { id: 'CWE-798', name: 'Hardcoded Credentials', description: 'The software contains hardcoded credentials such as passwords or keys.' },
  { id: 'CWE-200', name: 'Information Exposure', description: 'An information exposure vulnerability exists when an application reveals sensitive data.' },
  { id: 'CWE-287', name: 'Improper Authentication', description: 'The software does not properly verify the identity of the user.' },
  { id: 'CWE-306', name: 'Missing Authentication', description: 'The software does not perform authentication for critical functionality.' },
  { id: 'CWE-377', name: 'Insecure Temporary File', description: 'Creating and using insecure temporary files.' },
  { id: 'CWE-400', name: 'Uncontrolled Resource Consumption', description: 'The software does not properly control the allocation of resources.' },
  { id: 'CWE-732', name: 'Incorrect Permission Assignment', description: 'The software assigns incorrect permissions to a critical resource.' },
  { id: 'CWE-918', name: 'Server-Side Request Forgery (SSRF)', description: 'The web server receives a URL from an upstream component and retrieves its contents.' },
];
