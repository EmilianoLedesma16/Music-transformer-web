package controlador;

import util.Conexion;
import java.io.IOException;
import java.io.PrintWriter;
import java.sql.Connection;
import java.sql.SQLException;

import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@WebServlet("/ServletP")
public class ServletP extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        response.setContentType("text/html;charset=UTF-8");

        try (PrintWriter out = response.getWriter()) {
            out.println("<html>");
            out.println("<head><title>ServletP Test</title></head>");
            out.println("<body>");
            out.println("<h1>Servlet funcionando correctamente</h1>");

            try {
                Connection con = Conexion.getConexion();
                if (con != null && !con.isClosed()) {
                    out.println("<p style='color:green;'>Conexión a MySQL exitosa</p>");
                    con.close();
                } else {
                    out.println("<p style='color:red;'>No se pudo conectar a MySQL</p>");
                }
            } catch (SQLException e) {
                out.println("<p style='color:red;'>Error SQL: " + e.getMessage() + "</p>");
            } catch (Exception e) {
                out.println("<p style='color:red;'>Error general: " + e.getMessage() + "</p>");
            }

            out.println("</body>");
            out.println("</html>");
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        String nombre = request.getParameter("nombre");

        response.setContentType("text/html;charset=UTF-8");

        try (PrintWriter out = response.getWriter()) {
            out.println("<html><body>");
            out.println("<h1>Datos recibidos</h1>");
            out.println("<p>Nombre: " + nombre + "</p>");
            out.println("</body></html>");
        }
    }
}