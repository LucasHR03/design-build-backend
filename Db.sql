CREATE DATABASE IF NOT EXISTS gravid_app;
USE gravid_app;

-- Brugere
CREATE TABLE Bruger (
    bruger_id INT AUTO_INCREMENT PRIMARY KEY,
    cpr_nr VARCHAR(20) NOT NULL,
    navn VARCHAR(100) NOT NULL,
    pin_kode_hash VARCHAR(255) NOT NULL,
    oprettet_dato DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sessioner
CREATE TABLE Session (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
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

-- Kryptering
CREATE TABLE Patiens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    encrypted_cpr TEXT NOT NULL
);