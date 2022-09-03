import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Display portfolio
    userid = session["user_id"]
    portfolio = db.execute("SELECT * FROM portfolio WHERE id = ?", userid)
    value = 0
    # Create new list of dictionaries for final table in /index
    table = []
    length = len(portfolio)
    for x in range(length):
        dict = {}
        output = lookup(portfolio[x]['stocksymbol'])
        dict['name'] = output.get("name")
        dict['symbol'] = output.get("symbol")
        dict['shares'] = portfolio[x]['shares']
        dict['price'] = usd(output.get("price"))
        dict['value'] = usd(portfolio[x]['shares'] * output.get("price"))
        table.append(dict)
        # Portfolio Value
        value += portfolio[x]['shares'] * output.get("price")
    # Cash Balance
    user = db.execute("SELECT cash FROM users WHERE id = ?", userid)
    balance = user[0]['cash']
    # Grand Total
    total = balance + value
    return render_template("index.html", table=table, balance=usd(balance), value=usd(value), total=usd(total), portfolio=portfolio)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure number of shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # Ensure symbol is valid stock symbol
        lookupoutput = lookup(request.form.get("symbol"))
        if lookupoutput is None:
            return apology("invalid stock symbol", 400)

        # Ensure only positive integer was submitted
        try:
            input = int(request.form.get("shares"))
            if input <= 0:
                return apology("shares input is not a positive integer", 400)
        except:
            return apology("shares input is not an integer", 400)

        # Ensure user has enough cash to afford the stock
        userid = session["user_id"]
        stockprice = lookupoutput.get("price")
        symbol = lookupoutput.get("symbol")
        shares = int(request.form.get("shares"))
        user = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        cash = user[0]['cash']
        totalprice = stockprice * float(shares)
        if totalprice > cash:
            return apology("not enough cash", 400)

        # Allow user to buy the stock
        else:
            # Keep track of transaction
            db.execute("INSERT INTO transactions (id, stockname, stocksymbol, price, type, shares) VALUES (?)",
            (userid,
            lookupoutput.get("name"),
            symbol,
            usd(stockprice),
            'buy',
            shares,))

            # Update user portfolio
            # Check if stock is already in portfolio
            test = db.execute("SELECT shares FROM portfolio WHERE (id = ? AND stocksymbol = ?)", userid, symbol)

            # Stock is not in portfolio
            if not test:
                db.execute("INSERT INTO portfolio (id, stocksymbol, shares) VALUES (?)",
                    (userid,
                    symbol,
                    shares))

            # Stock is already in portfolio
            else:
                totalshares = test[0]['shares'] + shares
                db.execute("DELETE FROM portfolio WHERE (id = ? AND stocksymbol = ?)", userid, symbol)
                db.execute("INSERT INTO portfolio (id, stocksymbol, shares) VALUES (?)",
                    (userid,
                    symbol,
                    totalshares))

            # Update user cash balance
            newbalance = cash - totalprice
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newbalance, userid)
            return render_template("buy.html", newbalance=newbalance, shares=shares, stockprice=usd(stockprice), totalprice=usd(totalprice), balance=usd(newbalance))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Display portfolio
    userid = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE id = ?", userid)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Lookup {name:string, price: float, symbol:str}
        lookupoutput = lookup(request.form.get("symbol"))

        # Ensure lookup was successful
        if lookupoutput is None:
            return apology("lookup failed, stock does not exist", 400)

        else:
            return render_template("quote.html", name=lookupoutput.get('name'), price=usd(lookupoutput.get('price')), symbol=lookupoutput.get('symbol'))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 400)

        # Ensure password matches confirmation password
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation password do not match", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username is not already taken
        if len(rows) == 1:
            return apology("username is already taken", 400)

        # Add username and password to database
        hashedpassword = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=len(request.form.get("password")))
        db.execute("INSERT INTO users (username, hash) VALUES (?)", (request.form.get("username"), hashedpassword))

        # Remember which user has logged in
        rowss = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        session["user_id"] = rowss[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    userid = session["user_id"]
    portfolio = db.execute("SELECT stocksymbol FROM portfolio WHERE id = ?", userid)
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # Ensure only positive integer was submitted
        try:
            input = int(request.form.get("shares"))
            if input <= 0:
                return apology("shares input is not a positive integer", 400)
        except:
            return apology("shares input is not an integer", 400)

        # Set variables
        lookupoutput = lookup(request.form.get("symbol"))
        symbol = lookupoutput.get("symbol")
        shares = int(request.form.get("shares"))
        usershares = db.execute("SELECT shares FROM portfolio WHERE (id = ? AND stocksymbol = ?)", userid, symbol)
        ownedshares = usershares[0]['shares']
        stockprice = lookupoutput.get("price")
        totalprice = stockprice * float(shares)

        # User does not own enough stock as they are trying to sell
        if shares > ownedshares:
            return apology("cannot sell more shares than owned", 400)

        # Allow user to sell stock
        else:
            # Check current user cash balance
            user = db.execute("SELECT cash FROM users WHERE id = ?", userid)
            cash = user[0]['cash']

            # Update user cash balance
            newbalance = cash + totalprice
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newbalance, userid)

            # Keep track of transaction
            db.execute("INSERT INTO transactions (id, stockname, stocksymbol, price, type, shares) VALUES (?)",
            (userid,
            lookupoutput.get("name"),
            symbol,
            usd(stockprice),
            'sell',
            shares,))

            # Update user portfolio
            # Check if they still own some of that stock
            newsharecount = ownedshares - shares
            # No more stock left
            if newsharecount == 0:
                db.execute("DELETE FROM portfolio WHERE (id = ? AND stocksymbol = ?)", userid, symbol)
            # Some stock left
            else:
                db.execute("DELETE FROM portfolio WHERE (id = ? AND stocksymbol = ?)", userid, symbol)
                db.execute("INSERT INTO portfolio (id, stocksymbol, shares) VALUES (?)",
                    (userid,
                    symbol,
                    newsharecount))

            return render_template("sell.html", portfolio=portfolio, balance=usd(newbalance), shares=shares, stockprice=usd(stockprice), totalprice=usd(totalprice))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Dropdown menu
        return render_template("sell.html", portfolio=portfolio)

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Add cash to balance"""
    # Check user's current balance
    userid = session["user_id"]
    user = db.execute("SELECT cash FROM users WHERE id = ?", userid)
    cash = user[0]['cash']
    # POST request
    if request.method == "POST":

        # Ensure transfer amount was submitted
        if not request.form.get("amount"):
            return apology("must provide transfer amount", 400)

        # Ensure credit card number was submitted
        elif not request.form.get("card"):
            return apology("must provide credit card number", 400)

        # Check to make sure credit card is valid
        else:
            card = request.form.get("card")
            # Part 1
            l = [int(x) for x in str(card)]
            length = len(l)
            i = 1
            summ = 0
            tens = 0
            ones = 0
            while i <= ((len(l))//2):
                doubled = 2 * l[length-(2*i)]
                if doubled >= 10:
                    tens = 1
                    ones = doubled - 10
                else:
                    tens = 0
                    ones = doubled
                i += 1
                summ += tens + ones
            # Part 2
            y = length - 1
            summm = 0
            while y >= 0:
                summm += l[y]
                y -= 2
            total = summ + summm
            if total % 10 == 0:
                # american express
                if length == 15 and l[0] == 3 and (l[1] == 4 or l[1] == 7):
                    cardtype = 'American Express'
                # mastercard
                elif length == 16 and l[0] == 5 and (l[1] >= 1 and l[1] <= 5):
                    cardtype = 'Mastercard'
                # visa
                elif (length == 13 or length == 16) and l[0] == 4:
                    cardtype = 'Visa'
                else:
                    return apology("invalid credit card", 400)
            else:
                return apology("invalid credit card", 400)

        # Update user's new balance in users
        amount = float(request.form.get("amount"))
        balance = float(amount) + float(cash)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, userid)

        # Update transaction
        db.execute("INSERT INTO transactions (id, stockname, stocksymbol, price, type, shares) VALUES (?)",
        (userid,
        'N/A',
        'N/A',
        usd(amount),
        'add cash',
        'N/A',))

        return render_template("cash.html", cash=usd(cash), balance=usd(balance), amount=usd(float(amount)), cardtype=cardtype)

    else:
        return render_template("cash.html", cash=usd(cash))