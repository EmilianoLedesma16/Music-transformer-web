<%@page import="java.util.List"%>
<%@page import="modelo.Usuario"%>
<%@page contentType="text/html" pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Inicio</title>
</head>
<body>
    <h2>Lista de Usuarios</h2>

    <a href="registro.jsp">Nuevo Usuario</a>
    <br><br>

    <table border="1">
        <tr>
            <th>ID</th>
            <th>Nombre</th>
            <th>Usuario</th>
            <th>Contraseña</th>
            <th>Acciones</th>
        </tr>

        <%
            List<Usuario> lista = (List<Usuario>) request.getAttribute("listaUsuarios");
            if (lista != null) {
                for (Usuario u : lista) {
        %>
        <tr>
            <td><%= u.getId() %></td>
            <td><%= u.getNombre() %></td>
            <td><%= u.getUsername() %></td>
            <td><%= u.getPassword() %></td>
            <td>
                <a href="UsuarioServlet?accion=editar&id=<%= u.getId() %>">Editar</a>
                <a href="UsuarioServlet?accion=eliminar&id=<%= u.getId() %>">Eliminar</a>
            </td>
        </tr>
        <%
                }
            }
        %>
    </table>
</body>
</html>