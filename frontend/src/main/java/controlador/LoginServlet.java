    package controlador;

    import dao.UsuarioDAO;
    import java.io.IOException;
    import jakarta.servlet.ServletException;
    import jakarta.servlet.annotation.WebServlet;
    import jakarta.servlet.http.HttpServlet;
    import jakarta.servlet.http.HttpServletRequest;
    import jakarta.servlet.http.HttpServletResponse;
    import jakarta.servlet.http.HttpSession;

    @WebServlet("/LoginServlet")
    public class LoginServlet extends HttpServlet {

        private UsuarioDAO dao = new UsuarioDAO();

        @Override
        protected void doPost(HttpServletRequest request, HttpServletResponse response)
                throws ServletException, IOException {

            String username = request.getParameter("username");
            String password = request.getParameter("password");

            if (dao.validarLogin(username, password)) {
                HttpSession sesion = request.getSession();
                sesion.setAttribute("usuario", username);
                response.sendRedirect(request.getContextPath() + "/UsuarioServlet?accion=listar");
            } else {
                request.setAttribute("error", "Usuario o contraseña incorrectos");
                request.getRequestDispatcher("/login.jsp").forward(request, response);
            }
        }
    }