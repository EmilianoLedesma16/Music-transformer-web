package dao;

import modelo.Usuario;
import util.Conexion;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class UsuarioDAO {

    public boolean validarLogin(String username, String password) {
        String sql = "SELECT * FROM usuarios WHERE username = ? AND password = ?";

        try (Connection con = Conexion.getConnection();
                PreparedStatement ps = con.prepareStatement(sql)) {

            ps.setString(1, username);
            ps.setString(2, password);

            ResultSet rs = ps.executeQuery();
            return rs.next();

        } catch (SQLException e) {
            System.out.println("Error en validarLogin: " + e.getMessage());
            return false;
        }
    }

    public boolean insertar(Usuario u) {
        String sql = "INSERT INTO usuarios(username, password, nombre) VALUES(?,?,?)";
        System.out.println("holaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
        Connection con = null;
        PreparedStatement ps = null;

        try {
            con = Conexion.getConnection();

            if (con == null) {
                System.out.println("La conexion es null");
                return false;
            }

            if (u == null) {
                System.out.println("El usuario es null");
                return false;
            }

            System.out.println("Nombre: " + u.getNombre());
            System.out.println("Username: " + u.getUsername());
            System.out.println("Password: " + u.getPassword());

            ps = con.prepareStatement(sql);
            ps.setString(1, u.getUsername());
            ps.setString(2, u.getPassword());
            ps.setString(3, u.getNombre());

            return ps.executeUpdate() > 0;

        } catch (SQLException e) {
            System.out.println("Error SQL en insertar: " + e.getMessage());
            e.printStackTrace();
            return false;
        } catch (Exception e) {
            System.out.println("Error general en insertar: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            try {
                if (ps != null) {
                    ps.close();
                }
            } catch (Exception e) {
            }
            try {
                if (con != null) {
                    con.close();
                }
            } catch (Exception e) {
            }
        }
    }

    public List<Usuario> listar() {
        List<Usuario> lista = new ArrayList<>();
        String sql = "SELECT * FROM usuarios";

        try (Connection con = Conexion.getConnection();
                PreparedStatement ps = con.prepareStatement(sql);
                ResultSet rs = ps.executeQuery()) {

            while (rs.next()) {
                Usuario u = new Usuario();
                u.setId(rs.getInt("id"));
                u.setUsername(rs.getString("username"));
                u.setPassword(rs.getString("password"));
                u.setNombre(rs.getString("nombre"));
                lista.add(u);
            }

        } catch (SQLException e) {
            System.out.println("Error en listar: " + e.getMessage());
        }
        return lista;
    }

    public Usuario obtenerPorId(int id) {
        String sql = "SELECT * FROM usuarios WHERE id = ?";
        Usuario u = null;

        try (Connection con = Conexion.getConnection();
                PreparedStatement ps = con.prepareStatement(sql)) {

            ps.setInt(1, id);
            ResultSet rs = ps.executeQuery();

            if (rs.next()) {
                u = new Usuario();
                u.setId(rs.getInt("id"));
                u.setUsername(rs.getString("username"));
                u.setPassword(rs.getString("password"));
                u.setNombre(rs.getString("nombre"));
            }

        } catch (SQLException e) {
            System.out.println("Error en obtenerPorId: " + e.getMessage());
        }
        return u;
    }

    public boolean actualizar(Usuario u) {
        String sql = "UPDATE usuarios SET username=?, password=?, nombre=? WHERE id=?";

        try (Connection con = Conexion.getConnection();
                PreparedStatement ps = con.prepareStatement(sql)) {

            ps.setString(1, u.getUsername());
            ps.setString(2, u.getPassword());
            ps.setString(3, u.getNombre());
            ps.setInt(4, u.getId());

            return ps.executeUpdate() > 0;

        } catch (SQLException e) {
            System.out.println("Error en actualizar: " + e.getMessage());
            return false;
        }
    }

    public boolean eliminar(int id) {
        String sql = "DELETE FROM usuarios WHERE id=?";

        try (Connection con = Conexion.getConnection();
                PreparedStatement ps = con.prepareStatement(sql)) {

            ps.setInt(1, id);
            return ps.executeUpdate() > 0;

        } catch (SQLException e) {
            System.out.println("Error en eliminar: " + e.getMessage());
            return false;
        }
    }
}
