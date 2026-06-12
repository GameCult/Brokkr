# Brokkr Persona State

`brokkr.cc` is Brokkr's repo-local persistent Persona state.

Do not hand-edit the `.cc` file. Use the repo-local tools:

```powershell
.\tools\persona-state-read.ps1
.\tools\persona-remember.ps1 -Summary "..." -Claim "..." -ActionImplication "..."
```

The tools call VoidBot's typed self-state service so the same document schema used by registered repo Faces owns mutation and reads.

VoidBot automatic indexing requires Brokkr to be registered as a repo Face identity in VoidBot. Until then, this file is local typed state and can still be read or mutated by the tools here.
