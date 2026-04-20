package controlador;

import dao.UsuarioDAO;
import modelo.Usuario;
import java.io.IOException;
import java.util.List;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@WebServlet("/UsuarioServlet")
public class UsuarioServlet extends HttpServlet {

    private UsuarioDAO dao = new UsuarioDAO();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String accion = request.getParameter("accion");

        if (accion == null || accion.isEmpty()) {
            accion = "listar";
        }

        switch (accion) {
            case "listar":
                List<Usuario> lista = dao.listar();
                request.setAttribute("listaUsuarios", lista);
                request.getRequestDispatcher("/inicio.jsp").forward(request, response);
                break;

            case "editar":
                int idEditar = Integer.parseInt(request.getParameter("id"));
                Usuario usuario = dao.obtenerPorId(idEditar);
                request.setAttribute("usuario", usuario);
                request.getRequestDispatcher("/editar.jsp").forward(request, response);
                break;

            case "eliminar":
                int idEliminar = Integer.parseInt(request.getParameter("id"));
                dao.eliminar(idEliminar);
                response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
                break;

            default:
                response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
                break;
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String accion = request.getParameter("accion");

        if (accion == null) {
            response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
            return;
        }

        switch (accion) {
            case "insertar":
                String nombre = request.getParameter("nombre");
                String username = request.getParameter("username");
                String password = request.getParameter("password");

                Usuario nuevo = new Usuario();
                nuevo.setNombre(nombre);
                nuevo.setUsername(username);
                nuevo.setPassword(password);

                dao.insertar(nuevo);
                response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
                break;

            case "actualizar":
                int id = Integer.parseInt(request.getParameter("id"));
                String nombreEdit = request.getParameter("nombre");
                String usernameEdit = request.getParameter("username");
                String passwordEdit = request.getParameter("password");

                Usuario u = new Usuario();
                u.setId(id);
                u.setNombre(nombreEdit);
                u.setUsername(usernameEdit);
                u.setPassword(passwordEdit);

                dao.actualizar(u);
                response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
                break;

            default:
                response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
                break;
        }
    }
}