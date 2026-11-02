from flask import Flask, render_template


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template("store/home.html")

    @app.route("/shop")
    def shop():
        return render_template("store/shop.html")

    @app.route("/product")
    def product_detail():
        return render_template("store/product_detail.html")

    @app.route("/cart")
    def cart():
        return render_template("store/cart.html")

    @app.route("/checkout")
    def checkout():
        return render_template("checkout/checkout.html")

    @app.route("/order-success")
    def order_success():
        return render_template("checkout/order_success.html")

    @app.route("/login")
    def login():
        return render_template("auth/login.html")

    @app.route("/register")
    def register():
        return render_template("auth/register.html")

    @app.route("/forgot-password")
    def forgot_password():
        return render_template("auth/forgot_password.html")

    @app.route("/account")
    def profile():
        return render_template("account/profile.html")

    @app.route("/account/orders")
    def order_history():
        return render_template("account/order_history.html")

    @app.route("/account/address")
    def address():
        return render_template("account/address.html")

    @app.route("/account/wishlist")
    def wishlist():
        return render_template("account/wishlist.html")

    @app.route("/admin")
    def admin_dashboard():
        return render_template("admin/dashboard.html")

    @app.route("/admin/products")
    def admin_products():
        return render_template("admin/products.html")

    @app.route("/admin/orders")
    def admin_orders():
        return render_template("admin/orders.html")

    @app.route("/admin/users")
    def admin_users():
        return render_template("admin/users.html")

    return app
