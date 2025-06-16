CREATE DATABASE IF NOT EXISTS gravid_app;
USE gravid_app;

-- Brugere
CREATE TABLE Bruger (
    bruger_id INT AUTO_INCREMENT PRIMARY KEY,
    cpr_krypteret VARCHAR(512) NOT NULL, -- Bedre end TEXT til Fernet
    navn VARCHAR(100) NOT NULL,
    pin_kode_hash VARCHAR(255) NOT NULL,
    oprettet_dato DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sessioner
CREATE TABLE Session (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT NOT NULL,
    session_token VARCHAR(255) NOT NULL,
    udløbs_tidspunkt DATETIME NOT NULL,
    FOREIGN KEY (bruger_id) REFERENCES Bruger(bruger_id)
);

-- Ve-registreringer
CREATE TABLE VeRegistrering (
    ve_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
    start_tidspunkt DATETIME NOT NULL,
    slut_tidspunkt DATETIME NOT NULL,
    varighed INT, -- i sekunder
    interval_til_naeste INT, -- i sekunder
    FOREIGN KEY (bruger_id) REFERENCES Bruger(bruger_id)
);

-- Noter
CREATE TABLE Noter (
    noter_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
    tidspunkt DATETIME NOT NULL,
    noter_type VARCHAR(50),
    beskrivelse TEXT,
    FOREIGN KEY (bruger_id) REFERENCES Bruger(bruger_id)
);

-- Behandlingslog
CREATE TABLE BehandlingsLog (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
    handling VARCHAR(100),
    detaljer TEXT,
    tidspunkt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Opret bruger med begrænsede rettigheder
CREATE USER IF NOT EXISTS 've_app_user'@'localhost' IDENTIFIED BY 'et_sikkert_password';
GRANT SELECT, INSERT ON gravid_app.* TO 've_app_user'@'localhost';
