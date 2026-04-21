! C05: DO CONCURRENT loop
program do_concurrent
    implicit none
    integer, dimension(100) :: A, B
    integer :: i
    
    B = 10
    
    ! The construct below will be traced
    DO CONCURRENT (i = 1:100:2)
        A(i) = B(i) * 2
    END DO
end program do_concurrent
