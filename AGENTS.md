# AGENTS.md

Agentic coding instructions for PandaArchive repository.

## Project Overview

This is a new project (PandaArchive) with MIT License. Currently in early stages - establish patterns as you implement.

## Commands

Since this is a new repository without build configuration yet:

### To Be Determined
- **Build**: Add once build system is chosen
- **Test**: Add once test framework is configured
- **Lint**: Add once linter is configured
- **Format**: Add once formatter is configured

### Common Patterns (apply once configured)
```bash
# When adding build/test/lint, follow these patterns:
# Build: npm run build / cargo build / python -m build / make
# Test: npm test / cargo test / pytest / go test
# Test single file: npm test -- <file> / cargo test <name> / pytest <path>
# Lint: npm run lint / cargo clippy / ruff check / golangci-lint
# Format: npm run format / cargo fmt / black / gofmt
```

## Code Style Guidelines

### General Principles
- Write clear, readable code
- Prefer explicit over implicit
- Document public APIs and complex logic
- Keep functions small and focused

### Imports
- Group imports: stdlib → third-party → local
- Use absolute imports for local modules once structure is established
- Avoid circular dependencies

### Naming Conventions
- **Variables/Functions**: camelCase (JavaScript/TypeScript), snake_case (Python/Rust)
- **Classes/Types**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Private**: _prefix or m_ prefix based on language convention

### Types (when using typed languages)
- Prefer explicit types for public APIs
- Use strict mode when available
- Avoid `any`/`unknown` without proper guards
- Never use `@ts-ignore` or `@ts-expect-error` without explanation

### Error Handling
- Use exceptions for exceptional cases
- Return Result/Option types where idiomatic
- Always handle errors explicitly - no empty catch blocks
- Log errors with context before propagating

### Comments
- Document WHY, not WHAT (code shows what)
- Use Javadoc/Rustdoc style for public APIs
- Keep comments current with code changes

## Project Structure

```
PandaArchive/
├── .git/           # Git configuration
├── LICENSE         # MIT License
├── README.md       # Add project documentation
├── src/            # Add source code here
└── tests/          # Add tests here
```

## As You Implement

1. **Choose build tools** and update Commands section
2. **Add linting/formatting** config and document it here
3. **Establish testing patterns** and add single-test examples
4. **Document language-specific conventions** as they emerge

## File Creation Rules

When creating new files:
1. Add license header if required by project
2. Include brief file-level comment explaining purpose
3. Follow existing patterns in adjacent files
4. Update this AGENTS.md if introducing new conventions

## Testing Guidelines

Once testing is configured:
- Write tests for public APIs
- Aim for meaningful coverage, not 100% line coverage
- Test edge cases and error conditions
- Keep tests fast and deterministic
- Example single test command (update when known):
  ```bash
  # npm test -- <pattern>
  # cargo test <test_name>
  # pytest <path>::<test_name>
  ```

## Version Control

- Commit atomic, logical changes
- Write clear commit messages (imperative mood: "Add X" not "Added X")
- Don't commit secrets, build artifacts, or dependencies
- Update AGENTS.md when conventions change

---

*This file should evolve with the project. Update it as patterns solidify.*
