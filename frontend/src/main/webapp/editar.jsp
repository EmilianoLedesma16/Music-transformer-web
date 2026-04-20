<%@page import="modelo.Usuario"%>
<%@page contentType="text/html" pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Editar Usuario</title>
</head>
<body>
    <h2>Editar Usuario</h2>

    <%
        Usuario u = (Usuario) request.getAttribute("usuario");
    %>

    <form action="UsuarioServlet" method="post">
        <input type="hidden" name="accion" value="actualizar">
        <input type="hidden" name="id" value="<%= u.getId() %>">

        <label>Nombre:</label><br>
        <input type="text" name="nombre" value="<%= u.getNombre() %>" required><br><br>

        <label>Usuario:</label><br>
        <input type="text" name="username" value="<%= u.getUsername() %>" required><br><br>

        <label>Contraseña:</label><br>
        <input type="text" name="password" value="<%= u.getPassword() %>" required><br><br>

        <button type="submit">Actualizar</button>
    </form>

    <br>
    <a href="UsuarioServlet?accion=listar">Volver</a>
</body>
</html>