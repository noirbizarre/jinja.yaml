## 🚀 0.2.0 (2026-11-06)

### 💫 New features

- **api**: allow customizing the output mapping type in load helpers
- **merge**: add explicit configuration merge strategies ([#15](https://github.com/noirbizarre/jinja.yaml/issues/15))
- **resolver**: improve resolution error diagnostics ([#13](https://github.com/noirbizarre/jinja.yaml/issues/13))
- preserve configuration source locations and provenance ([#14](https://github.com/noirbizarre/jinja.yaml/issues/14))
- initial implementation of the jinja.yaml library

### 🐛 Bug fixes

- **loader**: strengthen validation and error reporting ([#11](https://github.com/noirbizarre/jinja.yaml/issues/11))
- **resolver**: improve dependency analysis and cycle diagnostics ([#10](https://github.com/noirbizarre/jinja.yaml/issues/10))
- preserve literal strings containing line prefixes
- distinguish raw documents from resolved result types
- surface release version computation failures
- measure coverage for jinja_yaml
- detect configured Jinja template syntax
- detect undefined values in native template containers
- resolve document keys that shadow Jinja globals

### 📖 Documentation

- correct template merge preservation comments
- clarify custom mapping output behavior
- explain native template literal conversion
- fix development task commands
- clarify local CI task coverage
- clarify the scope of JinjaYamlError

### 📦 Build

- **deps-dev**: update uv-build requirement from <0.13,>=0.12 to >=0.12,<0.14 ([#9](https://github.com/noirbizarre/jinja.yaml/issues/9))
- **deps-dev**: bump the python-dependencies group across 1 directory with 2 updates ([#7](https://github.com/noirbizarre/jinja.yaml/issues/7))
- **mise**: bootstrap the mise tooling
- derive version from Git tags via pdm-backend

### 🧹 Chores

- **tpl**: update template
- **tpl**: adopt https://github.com/noirbizarre/python.tpl template