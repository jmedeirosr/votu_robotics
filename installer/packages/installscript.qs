function Component() {
    component.loaded.connect(this, Component.prototype.installerLoaded);
}

Component.prototype.installerLoaded = function() {
    installer.setDefaultPageVisible(QInstaller.ComponentSelection, false);
};

Component.prototype.createOperations = function() {
    component.createOperations();

    component.addOperation(
        "CreateShortcut",
        "@TargetDir@/app/votu-fieldops",
        "@ApplicationsDir@/Votu FieldOps.desktop",
        "workingDirectory=@TargetDir@",
        "iconPath=@TargetDir@/votu-fieldops.png"
    );

    if (installer.value("os") === "x11") {
        component.addOperation(
            "CreateShortcut",
            "@TargetDir@/app/votu-fieldops",
            "@HomeDir@/Desktop/Votu FieldOps.desktop",
            "workingDirectory=@TargetDir@",
            "iconPath=@TargetDir@/votu-fieldops.png"
        );
    }

    component.addOperation("Mkdir", "@HomeDir@/.config/votu-fieldops");
    component.addOperation("Mkdir", "@HomeDir@/.config/votu-fieldops/logs");
};

