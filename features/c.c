#include <QApplication>
#include <QWidget>
#include <QGridLayout>
#include <QPushButton>
#include <QLineEdit>
#include <QString>

class Calculator : public QWidget {
    Q_OBJECT

public:
    Calculator(QWidget *parent = nullptr) : QWidget(parent) {
        setWindowTitle("Simple Calculator");
        setFixedSize(300, 400);

        display = new QLineEdit(this);
        display->setReadOnly(true);
        display->setAlignment(Qt::AlignRight);
        display->setText("0");
        display->setStyleSheet("font-size: 24px; padding: 10px;");

        QGridLayout *layout = new QGridLayout(this);
        layout->addWidget(display, 0, 0, 1, 4);

        // Button labels
        const char* buttons[16] = {
            "7", "8", "9", "/",
            "4", "5", "6", "*",
            "1", "2", "3", "-",
            "0", "C", "=", "+"
        };

        int pos = 0;
        for (int row = 1; row <= 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                QPushButton *btn = new QPushButton(buttons[pos], this);
                btn->setMinimumSize(60, 50);
                btn->setStyleSheet("font-size: 18px;");
                layout->addWidget(btn, row, col);

                connect(btn, &QPushButton::clicked, this, &Calculator::onButtonClicked);
                ++pos;
            }
        }

        setLayout(layout);
        currentValue = 0.0;
        pendingOperator = "";
        waitingForOperand = true;
    }

private slots:
    void onButtonClicked() {
        QPushButton *btn = qobject_cast<QPushButton*>(sender());
        if (!btn) return;

        QString text = btn->text();

        if (text >= "0" && text <= "9") {
            if (waitingForOperand) {
                display->setText(text);
                waitingForOperand = false;
            } else {
                display->setText(display->text() + text);
            }
        }
        else if (text == "C") {
            display->setText("0");
            currentValue = 0.0;
            pendingOperator = "";
            waitingForOperand = true;
        }
        else if (text == "=") {
            calculate();
            pendingOperator = "";
            waitingForOperand = true;
        }
        else { // operator
            if (!pendingOperator.isEmpty()) {
                calculate();
            } else {
                currentValue = display->text().toDouble();
            }
            pendingOperator = text;
            waitingForOperand = true;
        }
    }

private:
    void calculate() {
        double operand = display->text().toDouble();
        double result = currentValue;

        if (pendingOperator == "+")
            result = currentValue + operand;
        else if (pendingOperator == "-")
            result = currentValue - operand;
        else if (pendingOperator == "*")
            result = currentValue * operand;
        else if (pendingOperator == "/") {
            if (operand == 0.0) {
                display->setText("Error");
                waitingForOperand = true;
                pendingOperator = "";
                return;
            }
            result = currentValue / operand;
        }

        display->setText(QString::number(result, 'g', 12));
        currentValue = result;
    }

    QLineEdit *display;
    double currentValue;
    QString pendingOperator;
    bool waitingForOperand;
};

#include "calculator.moc"   // needed when using Q_OBJECT in a single .cpp file

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    Calculator calc;
    calc.show();
    return app.exec();
}
