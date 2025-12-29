fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Компилируем все proto файлы
    tonic_build::configure()
        .build_server(true)
        .build_client(true)
        .compile_protos(
            &[
                "../proto/api_gateway.proto",
                "../proto/director.proto",
                "../proto/file_gateway.proto",
            ],
            &["../proto"],
        )?;
    Ok(())
}

