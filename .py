"""
Library Management System (single-file Flask + SQLite)

Features:
- Add / Edit / Delete Books
- Add / Edit / Delete Members
- Borrow and Return books (loan records)
- Simple search and listing
- Minimal HTML UI rendered from templates (all in one file)

Run:
1. Install Flask: pip install flask
2. Run: python flask_sqlite.py
3. Open http://127.0.0.1:5000 in your browser

This is a simple demo suitable for learning and small use. For production, split files, use SQLAlchemy, add auth, validation, and tests.
"""
from flask import Flask, g, request, redirect, url_for, render_template_string, flash
import sqlite3
from datetime import datetime
import os

DATABASE = 'library.db'
app = Flask(__name__)
app.secret_key = 'replace-with-a-secure-key'

# ----------------- Database helpers -----------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        need_init = not os.path.exists(DATABASE)
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        if need_init:
            init_db(db)
    return db


def init_db(db):
    cur = db.cursor()
    cur.executescript('''
    CREATE TABLE books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        isbn TEXT UNIQUE,
        copies INTEGER DEFAULT 1
    );

    CREATE TABLE members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE
    );

    CREATE TABLE loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        borrowed_on TEXT NOT NULL,
        returned_on TEXT,
        FOREIGN KEY(book_id) REFERENCES books(id),
        FOREIGN KEY(member_id) REFERENCES members(id)
    );
    ''')
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ----------------- Utility functions -----------------

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    db.commit()
    return cur.lastrowid

# ----------------- Routes: Home / Search -----------------

HOME_HTML = """
<!doctype html>
<title>Library Management</title>
<h1>Library Management System</h1>
<p><a href="{{ url_for('list_books') }}">Books</a> | <a href="{{ url_for('list_members') }}">Members</a> | <a href="{{ url_for('list_loans') }}">Loans</a></p>
<form method="get" action="{{ url_for('search') }}">
  <input name="q" placeholder="Search books or members" value="{{ request.args.get('q','') }}">
  <button>Search</button>
</form>
<hr>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for m in messages %}
      <li>{{ m }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<p>Quick actions:</p>
<ul>
  <li><a href="{{ url_for('add_book') }}">Add book</a></li>
  <li><a href="{{ url_for('add_member') }}">Add member</a></li>
</ul>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    books = []
    members = []
    if q:
        books = query_db("SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?", (f'%{q}%', f'%{q}%', f'%{q}%'))
        members = query_db("SELECT * FROM members WHERE name LIKE ? OR email LIKE ?", (f'%{q}%', f'%{q}%'))
    return render_template_string('''
    <h2>Search results for "{{ q }}"</h2>
    <a href="{{ url_for('home') }}">Home</a>
    <h3>Books</h3>
    <ul>{% for b in books %}<li>{{ b['title'] }} by {{ b['author'] }} (copies: {{ b['copies'] }}) - <a href="{{ url_for('edit_book', book_id=b['id']) }}">Edit</a></li>{% else %}<li>No books</li>{% endfor %}</ul>
    <h3>Members</h3>
    <ul>{% for m in members %}<li>{{ m['name'] }} ({{ m['email'] }}) - <a href="{{ url_for('edit_member', member_id=m['id']) }}">Edit</a></li>{% else %}<li>No members</li>{% endfor %}</ul>
    ''', q=q, books=books, members=members)

# ----------------- Books -----------------

BOOKS_HTML = '''
<h2>Books</h2>
<a href="{{ url_for('home') }}">Home</a> | <a href="{{ url_for('add_book') }}">Add Book</a>
<ul>
{% for b in books %}
  <li>
    <strong>{{ b['title'] }}</strong> — {{ b['author'] }} (ISBN: {{ b['isbn'] or '-' }}) copies: {{ b['copies'] }}
    [<a href="{{ url_for('edit_book', book_id=b['id']) }}">edit</a>]
    [<a href="{{ url_for('delete_book', book_id=b['id']) }}" onclick="return confirm('Delete?');">delete</a>]
    [<a href="{{ url_for('borrow_book', book_id=b['id']) }}">borrow</a>]
  </li>
{% else %}
  <li>No books found.</li>
{% endfor %}
</ul>
'''

@app.route('/books')
def list_books():
    books = query_db('SELECT * FROM books ORDER BY title')
    return render_template_string(BOOKS_HTML, books=books)

ADD_BOOK_HTML = '''
<h2>Add Book</h2>
<a href="{{ url_for('list_books') }}">Back to books</a>
<form method="post">
  Title: <input name="title" required><br>
  Author: <input name="author"><br>
  ISBN: <input name="isbn"><br>
  Copies: <input name="copies" type="number" value="1" min="1"><br>
  <button>Add</button>
</form>
'''

@app.route('/books/add', methods=['GET','POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form.get('author','').strip()
        isbn = request.form.get('isbn','').strip() or None
        copies = int(request.form.get('copies',1))
        try:
            execute_db('INSERT INTO books (title,author,isbn,copies) VALUES (?,?,?,?)', (title,author,isbn,copies))
            flash('Book added')
            return redirect(url_for('list_books'))
        except sqlite3.IntegrityError:
            flash('ISBN must be unique')

    return render_template_string(ADD_BOOK_HTML)

EDIT_BOOK_HTML = '''
<h2>Edit Book</h2>
<a href="{{ url_for('list_books') }}">Back to books</a>
<form method="post">
  Title: <input name="title" value="{{ book['title'] }}" required><br>
  Author: <input name="author" value="{{ book['author'] }}"><br>
  ISBN: <input name="isbn" value="{{ book['isbn'] }}"><br>
  Copies: <input name="copies" type="number" value="{{ book['copies'] }}" min="1"><br>
  <button>Save</button>
</form>
'''

@app.route('/books/<int:book_id>/edit', methods=['GET','POST'])
def edit_book(book_id):
    book = query_db('SELECT * FROM books WHERE id=?', (book_id,), one=True)
    if not book:
        flash('Book not found')
        return redirect(url_for('list_books'))
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form.get('author','').strip()
        isbn = request.form.get('isbn','').strip() or None
        copies = int(request.form.get('copies',1))
        try:
            execute_db('UPDATE books SET title=?,author=?,isbn=?,copies=? WHERE id=?', (title,author,isbn,copies,book_id))
            flash('Book updated')
            return redirect(url_for('list_books'))
        except sqlite3.IntegrityError:
            flash('ISBN must be unique')
    return render_template_string(EDIT_BOOK_HTML, book=book)

@app.route('/books/<int:book_id>/delete')
def delete_book(book_id):
    execute_db('DELETE FROM books WHERE id=?', (book_id,))
    flash('Book deleted (if existed)')
    return redirect(url_for('list_books'))

# ----------------- Members -----------------

MEMBERS_HTML = '''
<h2>Members</h2>
<a href="{{ url_for('home') }}">Home</a> | <a href="{{ url_for('add_member') }}">Add Member</a>
<ul>
{% for m in members %}
  <li>{{ m['name'] }} ({{ m['email'] or '-' }}) [<a href="{{ url_for('edit_member', member_id=m['id']) }}">edit</a>] [<a href="{{ url_for('delete_member', member_id=m['id']) }}" onclick="return confirm('Delete?');">delete</a>]</li>
{% else %}
  <li>No members found.</li>
{% endfor %}
</ul>
'''

@app.route('/members')
def list_members():
    members = query_db('SELECT * FROM members ORDER BY name')
    return render_template_string(MEMBERS_HTML, members=members)

ADD_MEMBER_HTML = '''
<h2>Add Member</h2>
<a href="{{ url_for('list_members') }}">Back to members</a>
<form method="post">
  Name: <input name="name" required><br>
  Email: <input name="email" type="email"><br>
  <button>Add</button>
</form>
'''

@app.route('/members/add', methods=['GET','POST'])
def add_member():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form.get('email','').strip() or None
        try:
            execute_db('INSERT INTO members (name,email) VALUES (?,?)', (name,email))
            flash('Member added')
            return redirect(url_for('list_members'))
        except sqlite3.IntegrityError:
            flash('Email must be unique')
    return render_template_string(ADD_MEMBER_HTML)

EDIT_MEMBER_HTML = '''
<h2>Edit Member</h2>
<a href="{{ url_for('list_members') }}">Back to members</a>
<form method="post">
  Name: <input name="name" value="{{ member['name'] }}" required><br>
  Email: <input name="email" value="{{ member['email'] }}"><br>
  <button>Save</button>
</form>
'''

@app.route('/members/<int:member_id>/edit', methods=['GET','POST'])
def edit_member(member_id):
    member = query_db('SELECT * FROM members WHERE id=?', (member_id,), one=True)
    if not member:
        flash('Member not found')
        return redirect(url_for('list_members'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form.get('email','').strip() or None
        try:
            execute_db('UPDATE members SET name=?,email=? WHERE id=?', (name,email,member_id))
            flash('Member updated')
            return redirect(url_for('list_members'))
        except sqlite3.IntegrityError:
            flash('Email must be unique')
    return render_template_string(EDIT_MEMBER_HTML, member=member)

@app.route('/members/<int:member_id>/delete')
def delete_member(member_id):
    execute_db('DELETE FROM members WHERE id=?', (member_id,))
    flash('Member deleted (if existed)')
    return redirect(url_for('list_members'))

# ----------------- Loans -----------------

LOANS_HTML = '''
<h2>Loans</h2>
<a href="{{ url_for('home') }}">Home</a> | <a href="{{ url_for('list_books') }}">Books</a>
<table border="1" cellpadding="6">
<tr><th>Book</th><th>Member</th><th>Borrowed</th><th>Returned</th><th>Action</th></tr>
{% for l in loans %}
  <tr>
    <td>{{ l['title'] }}</td>
    <td>{{ l['name'] }}</td>
    <td>{{ l['borrowed_on'] }}</td>
    <td>{{ l['returned_on'] or '-' }}</td>
    <td>
      {% if not l['returned_on'] %}
        <a href="{{ url_for('return_book', loan_id=l['id']) }}">Return</a>
      {% else %}
        -
      {% endif %}
    </td>
  </tr>
{% else %}
  <tr><td colspan="5">No loans</td></tr>
{% endfor %}
</table>
'''

@app.route('/loans')
def list_loans():
    loans = query_db('''
        SELECT loans.id, loans.borrowed_on, loans.returned_on, books.title, members.name
        FROM loans JOIN books ON loans.book_id = books.id
                   JOIN members ON loans.member_id = members.id
        ORDER BY loans.borrowed_on DESC
    ''')
    return render_template_string(LOANS_HTML, loans=loans)

BORROW_HTML = '''
<h2>Borrow Book</h2>
<a href="{{ url_for('list_books') }}">Back</a>
<form method="post">
  Member: <select name="member_id">{% for m in members %}<option value="{{ m['id'] }}">{{ m['name'] }} ({{ m['email'] or '-' }})</option>{% endfor %}</select><br>
  <button>Borrow</button>
</form>
'''

@app.route('/books/<int:book_id>/borrow', methods=['GET','POST'])
def borrow_book(book_id):
    book = query_db('SELECT * FROM books WHERE id=?', (book_id,), one=True)
    if not book:
        flash('Book not found')
        return redirect(url_for('list_books'))
    members = query_db('SELECT * FROM members ORDER BY name')
    if request.method == 'POST':
        member_id = int(request.form['member_id'])
        # check copies available: copies - active loans
        active_loans = query_db('SELECT COUNT(*) as cnt FROM loans WHERE book_id=? AND returned_on IS NULL', (book_id,), one=True)['cnt']
        if active_loans >= book['copies']:
            flash('No copies available')
            return redirect(url_for('list_books'))
        execute_db('INSERT INTO loans (book_id,member_id,borrowed_on) VALUES (?,?,?)', (book_id, member_id, datetime.utcnow().isoformat()))
        flash('Book borrowed')
        return redirect(url_for('list_loans'))
    return render_template_string(BORROW_HTML, book=book, members=members)

@app.route('/loans/<int:loan_id>/return')
def return_book(loan_id):
    loan = query_db('SELECT * FROM loans WHERE id=?', (loan_id,), one=True)
    if not loan:
        flash('Loan not found')
        return redirect(url_for('list_loans'))
    if loan['returned_on']:
        flash('Already returned')
    else:
        execute_db('UPDATE loans SET returned_on=? WHERE id=?', (datetime.utcnow().isoformat(), loan_id))
        flash('Book returned')
    return redirect(url_for('list_loans'))

# ----------------- API endpoints (optional) -----------------

@app.route('/api/books')
def api_books():
    books = query_db('SELECT * FROM books')
    return {'books': [dict(b) for b in books]}

@app.route('/api/members')
def api_members():
    members = query_db('SELECT * FROM members')
    return {'members': [dict(m) for m in members]}

# ----------------- Run -----------------

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, g, request, redirect, url_for, render_template_string, flash
import sqlite3
from datetime import datetime
import os
import requests

DATABASE = 'library.db'
app = Flask(__name__)
app.secret_key = 'replace-with-a-secure-key'

# ----------------- Database helpers -----------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        need_init = not os.path.exists(DATABASE)
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        if need_init:
            init_db(db)
    return db


def init_db(db):
    cur = db.cursor()
    cur.executescript('''
    CREATE TABLE books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        isbn TEXT UNIQUE,
        copies INTEGER DEFAULT 1
    );

    CREATE TABLE members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE
    );

    CREATE TABLE loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        borrowed_on TEXT NOT NULL,
        returned_on TEXT,
        FOREIGN KEY(book_id) REFERENCES books(id),
        FOREIGN KEY(member_id) REFERENCES members(id)
    );
    ''')
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ----------------- Utility functions -----------------

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    db.commit()
    return cur.lastrowid

# ----------------- Routes: Home / Search -----------------

HOME_HTML = """
<!doctype html>
<title>Library Management</title>
<h1>Library Management System</h1>
<p><a href="{{ url_for('list_books') }}">Books</a> | <a href="{{ url_for('list_members') }}">Members</a> | <a href="{{ url_for('list_loans') }}">Loans</a> | <a href="{{ url_for('search_online') }}">Search & Add Book</a></p>
<form method="get" action="{{ url_for('search') }}">
  <input name="q" placeholder="Search books or members" value="{{ request.args.get('q','') }}">
  <button>Search</button>
</form>
<hr>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for m in messages %}
      <li>{{ m }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<p>Quick actions:</p>
<ul>
  <li><a href="{{ url_for('add_book') }}">Add book</a></li>
  <li><a href="{{ url_for('add_member') }}">Add member</a></li>
</ul>
"""

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/search_online', methods=['GET', 'POST'])
def search_online():
    SEARCH_HTML = """
    <h2>Search Books Online</h2>
    <a href="{{ url_for('home') }}">Home</a>
    <form method="get">
      Query: <input name="q" value="{{ request.args.get('q','') }}">
      <button>Search</button>
    </form>
    {% if books %}
      <h3>Results:</h3>
      <ul>
      {% for b in books %}
        <li>
          <strong>{{ b['title'] }}</strong> by {{ b['authors'] }} (ISBN: {{ b['isbn'] or '-' }})
          <form method="post" style="display:inline;">
            <input type="hidden" name="title" value="{{ b['title'] }}">
            <input type="hidden" name="author" value="{{ b['authors'] }}">
            <input type="hidden" name="isbn" value="{{ b['isbn'] }}">
            <button>Add to Library</button>
          </form>
        </li>
      {% endfor %}
      </ul>
    {% endif %}
    """
    books = []
    if request.method == 'POST':
        # Add selected book to library
        title = request.form['title']
        author = request.form['author']
        isbn = request.form.get('isbn') or None
        try:
            execute_db('INSERT INTO books (title,author,isbn,copies) VALUES (?,?,?)', (title, author, isbn, 1))
            flash('Book added to library')
        except Exception as e:
            flash(f'Error adding book: {e}')
        return redirect(url_for('list_books'))

    q = request.args.get('q', '').strip()
    if q:
        r = requests.get('https://www.googleapis.com/books/v1/volumes', params={'q': q, 'maxResults': 5})
        data = r.json()
        for item in data.get('items', []):
            volume = item['volumeInfo']
            books.append({
                'title': volume.get('title', 'Unknown'),
                'authors': ', '.join(volume.get('authors', [])),
                'isbn': next((i['identifier'] for i in volume.get('industryIdentifiers', []) if i['type']=='ISBN_13'), None)
            })

    return render_template_string(SEARCH_HTML, books=books)

# ----------------- Include all previous LMS routes here -----------------
# (Books, Members, Loans, API endpoints, etc.)

if __name__ == '__main__':
    app.run(debug=True)
