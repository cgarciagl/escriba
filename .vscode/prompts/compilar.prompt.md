---
name: compilar
description: "Compilar el proyecto Escriba y regenerar el ejecutable dist\Escriba.exe usando Escriba.spec."
---

Usa este prompt para ejecutar la compilación completa del proyecto Escriba y reconstruir el EXE.

Instrucciones:

1. Si `Escriba.exe` está en ejecución, ciérralo antes de compilar.
2. Desde la raíz del proyecto, ejecuta `pyinstaller Escriba.spec --clean --noconfirm`.
3. Verifica que la compilación termine con exit code 0.
4. No modifiques `config.json`, ya que se genera en tiempo de ejecución.
5. Si la compilación falla, detén el proceso y reporta el error al usuario.
6. Si la compilación es exitosa, confirma que `dist\Escriba.exe` se ha actualizado correctamente.
7. Ejecutar el nuevo exe.

Ejemplos de uso:

- "Compilar el proyecto y generar de nuevo el exe"
- "Reconstruir el ejecutable dist\\Escriba.exe usando la especificación Escriba.spec"
